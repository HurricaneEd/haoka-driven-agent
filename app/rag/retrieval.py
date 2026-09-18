"""混合检索服务：向量 MMR + 中文友好的 BM25 + RRF 融合。"""

from collections import Counter
import math
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from langchain_core.documents import Document

from app.rag.stores import ChromaVectorStore


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
        fetch_k: int = 30,
        lambda_mult: float = 0.7,
        spread_threshold: int = 3,
        hybrid_enabled: bool = True,
        lexical_weight: float = 0.35,
        rrf_k: int = 60,
    ) -> None:
        self.store = store
        self.fetch_k = fetch_k
        self.lambda_mult = lambda_mult
        self.spread_threshold = spread_threshold
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
        return self._deduplicate(ranked[:k])

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

    def _deduplicate(self, documents: Sequence[Document]) -> List[Document]:
        doc_ids = [
            str(document.metadata.get("doc_id"))
            for document in documents
            if document.metadata.get("doc_id")
        ]
        if len(set(doc_ids)) < self.spread_threshold:
            return list(documents)
        seen: set[str] = set()
        result: list[Document] = []
        for document in documents:
            doc_id = str(document.metadata.get("doc_id") or "")
            if not doc_id or doc_id in seen:
                continue
            seen.add(doc_id)
            result.append(document)
        return result
