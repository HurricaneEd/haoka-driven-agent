from tempfile import TemporaryDirectory
import unittest

from langchain_core.embeddings import Embeddings

from app.rag.chunkers import ChunkingConfig, StructureAwareChunker
from app.rag.ingestion import IngestionService
from app.rag.stores import ChromaVectorStore


class ToggleEmbeddings(Embeddings):
    def __init__(self):
        self.fail = False

    def _vectors(self, texts):
        if self.fail:
            raise RuntimeError("embedding unavailable")
        return [
            [
                float(len(text) % 17 + 1),
                float(sum(ord(char) for char in text) % 23 + 1),
                float(text.count("流量") + 1),
            ]
            for text in texts
        ]

    def embed_documents(self, texts):
        return self._vectors(texts)

    def embed_query(self, text):
        return self._vectors([text])[0]


class ChromaStoreTests(unittest.TestCase):
    def test_document_hash_skip_and_failure_safe_replace(self):
        with TemporaryDirectory(ignore_cleanup_errors=True) as directory:
            embeddings = ToggleEmbeddings()
            store = ChromaVectorStore(embeddings, directory)
            service = IngestionService(
                store=store,
                chunker=StructureAwareChunker(ChunkingConfig(256, 32)),
            )
            first = service.prepare_text(
                doc_id="plan-a",
                title="套餐 A",
                content="## 流量\n每月 100G 通用流量。",
                category="product",
            )
            self.assertEqual(service.ingest(first).status, "indexed")
            self.assertEqual(service.ingest(first).status, "skipped")
            self.assertEqual(store.get_document_hash("plan-a"), first.document.content_hash)
            self.assertEqual(store.count(), 1)

            changed = service.prepare_text(
                doc_id="plan-a",
                title="套餐 A",
                content="## 流量\n每月 120G 通用流量。",
                category="product",
            )
            embeddings.fail = True
            with self.assertRaisesRegex(RuntimeError, "embedding unavailable"):
                service.ingest(changed)

            self.assertEqual(store.count(), 1)
            self.assertEqual(store.get_document_hash("plan-a"), first.document.content_hash)


if __name__ == "__main__":
    unittest.main()
