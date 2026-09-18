import unittest

from langchain_core.documents import Document

from app.rag.retrieval import RetrievalService, lexical_tokens


def knowledge(doc_id, content, section="说明", category="product"):
    return Document(
        page_content=content,
        metadata={
            "doc_id": doc_id,
            "content_hash": f"hash-{doc_id}-{section}",
            "title": doc_id,
            "section": section,
            "category": category,
            "tags": "",
            "source": f"{doc_id}.md",
        },
    )


class FakeRetrievalStore:
    def __init__(self, vector_documents, all_documents):
        self.vector_documents = vector_documents
        self.all_documents = all_documents

    def mmr_search(self, query, *, k, fetch_k, lambda_mult, category=None):
        return [
            document for document in self.vector_documents
            if not category or document.metadata["category"] == category
        ][:k]

    def get_all_documents(self):
        return list(self.all_documents)


class HybridRetrievalTests(unittest.TestCase):
    def test_chinese_tokenizer_keeps_numbers_and_bigrams(self):
        tokens = lexical_tokens("四川联通 160G 套餐")
        self.assertIn("四川", tokens)
        self.assertIn("联通", tokens)
        self.assertIn("160g", tokens)

    def test_exact_lexical_match_promotes_vector_candidate(self):
        generic = knowledge("generic", "全国流量套餐介绍")
        other = knowledge("other", "订单物流与配送说明")
        exact = knowledge("sichuan", "四川联通每月 160G 通用流量，月租 30 元")
        store = FakeRetrievalStore([generic, other, exact], [generic, other, exact])
        service = RetrievalService(
            store,
            fetch_k=3,
            hybrid_enabled=True,
            lexical_weight=0.45,
        )
        result = service.retrieve("四川联通 160G", k=3)
        self.assertEqual(result[0].metadata["doc_id"], "sichuan")

    def test_category_filter_applies_to_both_rankings(self):
        product = knowledge("product-a", "注销方式", category="product")
        policy = knowledge("policy-a", "注销流程", category="policy")
        store = FakeRetrievalStore([policy, product], [policy, product])
        service = RetrievalService(store, fetch_k=2)
        result = service.retrieve("注销", k=2, category="product")
        self.assertEqual([item.metadata["doc_id"] for item in result], ["product-a"])


if __name__ == "__main__":
    unittest.main()
