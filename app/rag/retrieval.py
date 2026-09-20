"""混合检索服务：向量 MMR + 中文友好的 BM25 + RRF 融合。"""

from collections import Counter
import math
import re
from typing import Any, Dict, List, Optional, Protocol, Sequence, Tuple

from langchain_core.documents import Document

from app.rag.stores import ChromaVectorStore
from app.rag.identity import normalize_identity_text
from app.rag.schemas import RagDocument


class ParentStore(Protocol):
    def get(self, doc_id: str) -> RagDocument | None:
        ...

    def list(self, category: str | None = None) -> List[RagDocument]:
        ...


def lexical_tokens(text: str) -> List[str]:
    """保留英文/数字词，并为中文生成单字和双字词。"""
    tokens: list[str] = []
    for part in re.findall(r"[a-zA-Z0-9]+|[\u3400-\u9fff]+", text.lower()):
        if re.fullmatch(r"[\u3400-\u9fff]+", part):
            tokens.extend(part)
            tokens.extend(part[index:index + 2] for index in range(len(part) - 1))
        else:
            tokens.append(part)
    return tokens


class RetrievalService:
    def __init__(
        self,
        store: ChromaVectorStore,
        *,
        parent_store: ParentStore | None = None,
        fetch_k: int = 30,
        lambda_mult: float = 0.7,
        hybrid_enabled: bool = True,
        lexical_weight: float = 0.35,
        rrf_k: int = 60,
    ) -> None:
        self.store = store
        self.parent_store = parent_store
        self.fetch_k = fetch_k
        self.lambda_mult = lambda_mult
        self.hybrid_enabled = hybrid_enabled
        self.lexical_weight = max(0.0, min(1.0, lexical_weight))
        self.rrf_k = max(1, rrf_k)

    def retrieve(
        self, query: str, *, k: int = 6, category: Optional[str] = None
    ) -> List[Document]:
        if not query.strip() or k <= 0:
            return []
        candidate_count = max(k, self.fetch_k)
        vector_docs = self.store.mmr_search(
            query,
            k=candidate_count,
            fetch_k=max(candidate_count, self.fetch_k),
            lambda_mult=self.lambda_mult,
            category=category,
        )
        if self.hybrid_enabled:
            lexical_docs = self._lexical_rank(query, category, candidate_count)
            ranked = self._rrf(vector_docs, lexical_docs)
        else:
            ranked = vector_docs
        if not self.parent_store:
            return ranked[:k]
        return self._select_and_expand(query, ranked, k=k, category=category)

    def search(
        self, query: str, *, k: int = 5, category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        results: list[Dict[str, Any]] = []
        for document in self.retrieve(query, k=k, category=category):
            content = document.page_content
            if len(content) > 500:
                content = content[:500] + "..."
            metadata = document.metadata
            results.append({
                "content": content,
                "metadata": {
                    "doc_id": metadata.get("doc_id"),
                    "title": metadata.get("title"),
                    "section": metadata.get("section"),
                    "chunk_index": metadata.get("chunk_index"),
                    "category": metadata.get("category"),
                    "tags": [
                        value.strip()
                        for value in (metadata.get("tags") or "").split(",")
                        if value.strip()
                    ],
                    "source": metadata.get("source"),
                },
            })
        return results

    def _lexical_rank(
        self, query: str, category: Optional[str], limit: int
    ) -> List[Document]:
        documents = [
            document for document in self.store.get_all_documents()
            if not category or document.metadata.get("category") == category
        ]
        query_terms = lexical_tokens(query)
        if not documents or not query_terms:
            return []

        corpus: list[list[str]] = []
        document_frequencies: Counter[str] = Counter()
        for document in documents:
            metadata_text = " ".join(str(document.metadata.get(key) or "") for key in ("title", "section", "tags"))
            terms = lexical_tokens(f"{metadata_text} {document.page_content}")
            corpus.append(terms)
            document_frequencies.update(set(terms))

        average_length = sum(len(terms) for terms in corpus) / max(1, len(corpus))
        query_frequency = Counter(query_terms)
        scores: list[Tuple[float, Document]] = []
        k1, b = 1.5, 0.75
        document_count = len(documents)
        for document, terms in zip(documents, corpus):
            frequencies = Counter(terms)
            length_normalizer = k1 * (1 - b + b * len(terms) / max(1.0, average_length))
            score = 0.0
            for term, query_count in query_frequency.items():
                frequency = frequencies.get(term, 0)
                if not frequency:
                    continue
                document_frequency = document_frequencies[term]
                inverse_frequency = math.log(
                    1 + (document_count - document_frequency + 0.5)
                    / (document_frequency + 0.5)
                )
                score += query_count * inverse_frequency * (
                    frequency * (k1 + 1) / (frequency + length_normalizer)
                )
            if score > 0:
                scores.append((score, document))
        scores.sort(key=lambda item: item[0], reverse=True)
        return [document for _score, document in scores[:limit]]

    def _rrf(
        self,
        vector_documents: Sequence[Document],
        lexical_documents: Sequence[Document],
    ) -> List[Document]:
        scores: Dict[Tuple[str, str], float] = {}
        documents: Dict[Tuple[str, str], Document] = {}
        vector_weight = 1.0 - self.lexical_weight
        for rank, document in enumerate(vector_documents, 1):
            key = self._document_key(document)
            documents[key] = document
            scores[key] = scores.get(key, 0.0) + vector_weight / (self.rrf_k + rank)
        for rank, document in enumerate(lexical_documents, 1):
            key = self._document_key(document)
            documents[key] = document
            scores[key] = scores.get(key, 0.0) + self.lexical_weight / (self.rrf_k + rank)
        ranked_keys = sorted(scores, key=scores.get, reverse=True)
        return [documents[key] for key in ranked_keys]

    @staticmethod
    def _document_key(document: Document) -> Tuple[str, str]:
        metadata = document.metadata
        return (
            str(metadata.get("doc_id") or ""),
            str(metadata.get("content_hash") or document.page_content),
        )

    @staticmethod
    def _is_comparison(query: str) -> bool:
        return bool(re.search(r"对比|比较|区别|差别|哪个好|哪款|有哪些|推荐|怎么选", query))

    def _select_and_expand(
        self,
        query: str,
        ranked: Sequence[Document],
        *,
        k: int,
        category: Optional[str],
    ) -> List[Document]:
        parents = self.parent_store.list(category)
        if not parents:
            return list(ranked[:k])

        normalized_query = normalize_identity_text(query)
        explicit: list[RagDocument] = []
        for parent in parents:
            aliases = sorted(parent.aliases, key=lambda value: len(normalize_identity_text(value)), reverse=True)
            if any(
                len(normalize_identity_text(alias)) >= 2
                and normalize_identity_text(alias) in normalized_query
                for alias in aliases
            ):
                explicit.append(parent)

        comparison = self._is_comparison(query)
        if len(explicit) == 1:
            return [self._expand_parent(explicit[0], ranked)]
        if len(explicit) > 1:
            if comparison:
                return [self._expand_parent(parent, ranked) for parent in explicit[:3]]
            return [self._clarification(explicit)]

        ranked_ids: list[str] = []
        for document in ranked:
            doc_id = str(document.metadata.get("doc_id") or "")
            if doc_id and doc_id not in ranked_ids:
                ranked_ids.append(doc_id)
        candidates = [parent for doc_id in ranked_ids if (parent := self.parent_store.get(doc_id))]
        if not candidates:
            return list(ranked[:k])
        if comparison:
            return [self._expand_parent(parent, ranked) for parent in candidates[:3]]
        if len(candidates) > 1 and any(parent.category == "product" for parent in candidates):
            return [self._clarification(candidates[:5])]
        return [self._expand_parent(candidates[0], ranked)]

    @staticmethod
    def _expand_parent(parent: RagDocument, ranked: Sequence[Document]) -> Document:
        sections = list(dict.fromkeys(
            str(document.metadata.get("section") or "")
            for document in ranked
            if document.metadata.get("doc_id") == parent.doc_id
            and document.metadata.get("section")
        ))
        return Document(
            page_content=parent.content,
            metadata={
                "doc_id": parent.doc_id,
                "title": parent.title,
                "category": parent.category,
                "tags": ",".join(parent.tags),
                "aliases": ",".join(parent.aliases),
                "source": parent.source,
                "parent_chunk": True,
                "matched_sections": sections,
            },
        )

    @staticmethod
    def _clarification(candidates: Sequence[RagDocument]) -> Document:
        titles = [parent.title for parent in candidates]
        return Document(
            page_content=(
                "需要确认商品：当前问题未明确具体商品，请先向用户确认商品名称，不要直接给出套餐结论。"
                f"可能涉及：{'、'.join(titles)}。"
            ),
            metadata={
                "clarification_required": True,
                "candidate_titles": titles,
                "title": "需要确认商品",
                "category": "clarification",
            },
        )
