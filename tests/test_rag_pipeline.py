from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.rag.chunkers import ChunkingConfig, StructureAwareChunker
from app.rag.ingestion import IngestionService
from app.rag.parsers import DocumentParserRegistry, UnsupportedDocumentError
from app.rag.retrieval import RetrievalService
from app.rag.schemas import RagDocument
from langchain_core.documents import Document


class FakeStore:
    def __init__(self) -> None:
        self.hashes = {}
        self.documents = {}
        self.replace_calls = 0

    def get_document_hash(self, doc_id):
        return self.hashes.get(doc_id)

    def replace_document(self, doc_id, chunks):
        self.replace_calls += 1
        self.documents[doc_id] = list(chunks)
        self.hashes[doc_id] = chunks[0].document_hash

    def delete_document(self, doc_id):
        chunks = self.documents.pop(doc_id, [])
        self.hashes.pop(doc_id, None)
        return len(chunks)


class RagPipelineTests(unittest.TestCase):
    def test_markdown_parser_uses_filename_and_h1_without_frontmatter(self):
        raw = """# **测试套餐**

## 资费

月租 30 元。
"""
        with TemporaryDirectory() as directory:
            path = Path(directory) / "card-a.md"
            path.write_text(raw, encoding="utf-8")
            document = DocumentParserRegistry().parse(path, {"category": "product"})
        self.assertEqual(document.doc_id, "card-a")
        self.assertEqual(document.title, "测试套餐")
        self.assertEqual(document.category, "product")
        self.assertIn("测试套餐", document.aliases)

    def test_sichuan_product_aliases_are_derived_from_title(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "sichuan-liantong-160g.md"
            path.write_text("# 四川联通30元160G通用+100分钟【只发四川】", encoding="utf-8")
            document = DocumentParserRegistry().parse(path, {"category": "product"})
        self.assertIn("四川卡", document.aliases)
        self.assertIn("四川联通卡", document.aliases)
        self.assertIn("联通四川卡", document.aliases)
        self.assertNotIn("联通卡", document.aliases)

    def test_structure_first_then_size_fallback(self):
        document = RagDocument(
            doc_id="doc-a",
            title="套餐 A",
            content="# 套餐 A\n\n## 资费\n\n" + "每月包含通用流量。" * 80,
            source="test.md",
            category="product",
        )
        chunks = StructureAwareChunker(ChunkingConfig(180, 30)).split(document)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk.content) <= 180 for chunk in chunks))
        self.assertTrue(all(chunk.section == "资费" for chunk in chunks))
        self.assertTrue(all(chunk.content.startswith("套餐 A\n资费") for chunk in chunks))

    def test_chunk_ids_do_not_depend_on_position(self):
        chunker = StructureAwareChunker(ChunkingConfig(256, 32))
        original = RagDocument(
            doc_id="stable",
            title="套餐",
            content="# 套餐\n## 资费\n30 元\n## 激活\n实名认证",
            source="test.md",
        )
        changed = RagDocument(
            doc_id="stable",
            title="套餐",
            content="# 套餐\n## 介绍\n长期套餐\n## 资费\n30 元\n## 激活\n实名认证",
            source="test.md",
        )
        first = {chunk.section: chunk.id for chunk in chunker.split(original)}
        second = {chunk.section: chunk.id for chunk in chunker.split(changed)}
        self.assertEqual(first["资费"], second["资费"])
        self.assertEqual(first["激活"], second["激活"])

    def test_markdown_headings_inside_code_fence_are_not_sections(self):
        document = RagDocument(
            doc_id="code-doc",
            title="接口说明",
            content="# 接口说明\n## 示例\n```markdown\n## 这不是章节\n```\n调用示例。",
            source="api.md",
        )
        chunks = StructureAwareChunker(ChunkingConfig(256, 32)).split(document)
        self.assertEqual({chunk.section for chunk in chunks}, {"示例"})
        self.assertIn("## 这不是章节", chunks[0].content)

    def test_only_md_files_are_supported(self):
        registry = DocumentParserRegistry()
        self.assertEqual(registry.supported_suffixes, (".md",))
        with TemporaryDirectory() as directory:
            for suffix in (".markdown", ".txt", ".html", ".csv", ".pdf", ".docx", ".xlsx"):
                path = Path(directory) / f"unsupported{suffix}"
                path.write_text("test", encoding="utf-8")
                with self.assertRaises(UnsupportedDocumentError):
                    registry.parse(path)

    def test_ingestion_skips_unchanged_document(self):
        store = FakeStore()
        service = IngestionService(store=store)
        prepared = service.prepare_text(
            doc_id="manual-a",
            title="注销说明",
            content="可在运营商 APP 内申请注销。",
        )
        first = service.ingest(prepared)
        second = service.ingest(prepared)
        self.assertEqual(first.status, "indexed")
        self.assertEqual(second.status, "skipped")
        self.assertEqual(store.replace_calls, 1)
        self.assertEqual(service.delete("manual-a"), 1)


class FakeRetrievalStore:
    def __init__(self, documents):
        self.documents = documents

    def mmr_search(self, *_args, **_kwargs):
        return self.documents

    def get_all_documents(self):
        return self.documents


class FakeParentStore:
    def __init__(self, parents):
        self.parents = {parent.doc_id: parent for parent in parents}

    def get(self, doc_id):
        return self.parents.get(doc_id)

    def list(self, category=None):
        return [
            parent for parent in self.parents.values()
            if not category or parent.category == category
        ]


class ParentChildRetrievalTests(unittest.TestCase):
    def setUp(self):
        self.sichuan = RagDocument(
            doc_id="sichuan", title="四川联通30元160G通用+100分钟【只发四川】",
            content="四川卡完整资料：仅发四川。激活后使用。", source="product/sichuan.md",
            category="product", aliases=("四川联通", "四川联通卡", "四川卡", "联通四川卡"),
        )
        self.qingshui = RagDocument(
            doc_id="qingshui", title="联通清水卡29元155G全国【只发甘肃】",
            content="清水卡完整资料：只发甘肃。", source="product/qingshui.md",
            category="product", aliases=("联通清水卡", "清水卡"),
        )
        self.yunshu = RagDocument(
            doc_id="yunshu", title="联通云舒卡39元270G+100分钟【发全国】",
            content="云舒卡完整资料：全国发货。", source="product/yunshu.md",
            category="product", aliases=("联通云舒卡", "云舒卡"),
        )
        children = [
            Document(page_content="四川卡 激活", metadata={"doc_id": "sichuan", "section": "激活"}),
            Document(page_content="清水卡 注销", metadata={"doc_id": "qingshui", "section": "注销"}),
            Document(page_content="云舒卡 资费", metadata={"doc_id": "yunshu", "section": "资费"}),
        ]
        self.retrieval = RetrievalService(
            FakeRetrievalStore(children),
            parent_store=FakeParentStore((self.sichuan, self.qingshui, self.yunshu)),
            hybrid_enabled=False,
        )

    def test_explicit_alias_expands_only_matching_parent(self):
        result = self.retrieval.retrieve("四川卡怎么激活")
        self.assertEqual([item.metadata["doc_id"] for item in result], ["sichuan"])
        self.assertEqual(result[0].page_content, self.sichuan.content)

    def test_region_word_does_not_override_explicit_product(self):
        result = self.retrieval.retrieve("清水卡在四川能办吗")
        self.assertEqual([item.metadata["doc_id"] for item in result], ["qingshui"])

    def test_generic_carrier_question_requires_clarification(self):
        result = self.retrieval.retrieve("联通卡怎么注销")
        self.assertTrue(result[0].metadata["clarification_required"])

    def test_comparison_can_expand_multiple_named_products(self):
        result = self.retrieval.retrieve("四川卡和云舒卡有什么区别")
        self.assertEqual({item.metadata["doc_id"] for item in result}, {"sichuan", "yunshu"})


if __name__ == "__main__":
    unittest.main()
