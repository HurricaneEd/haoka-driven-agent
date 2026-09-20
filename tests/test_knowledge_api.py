from pathlib import Path
from tempfile import TemporaryDirectory
import os
import unittest


_temporary = TemporaryDirectory(ignore_cleanup_errors=True)
_root = Path(_temporary.name)
os.environ["DATABASE_URL"] = "sqlite:///" + (_root / "api.db").as_posix()
os.environ["CHROMA_DB_PATH"] = str(_root / "chroma")
os.environ["KNOWLEDGE_UPLOAD_PATH"] = str(_root / "uploads")
os.environ["DEBUG"] = "false"

from fastapi.testclient import TestClient

import app.api as api_module
import app.knowledge_documents as document_service
from app.database import DatabaseManager, SessionLocal
from app.rag.chunkers import ChunkingConfig, StructureAwareChunker
from app.rag.ingestion import IngestionService


class FakeKnowledgeBase:
    def __init__(self):
        self.pipeline = IngestionService(
            store=None,
            chunker=StructureAwareChunker(ChunkingConfig(256, 32)),
        )
        self.deleted = []

    def prepare_file(self, path, metadata):
        return self.pipeline.prepare_file(path, metadata)

    def ingest(self, prepared):
        return None

    def delete_document(self, doc_id):
        self.deleted.append(doc_id)
        return 0


class KnowledgeApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fake_kb = FakeKnowledgeBase()
        document_service.get_knowledge_base = lambda: cls.fake_kb
        api_module.process_knowledge_document = lambda doc_id: None
        cls.client_context = TestClient(api_module.app)
        cls.client = cls.client_context.__enter__()
        response = cls.client.post(
            "/auth/register",
            json={"email": "operator@example.com", "password": "secure-pass-123"},
        )
        cls.token = response.json()["token"]
        cls.headers = {"Authorization": f"Bearer {cls.token}"}

    @classmethod
    def tearDownClass(cls):
        cls.client_context.__exit__(None, None, None)
        _temporary.cleanup()

    def test_upload_process_list_retry_and_delete(self):
        upload = self.client.post(
            "/knowledge/documents",
            headers=self.headers,
            files={"file": ("policy.md", b"# Policy\n\n## Refund\n\nContact support.", "text/markdown")},
            data={"title": "Refund policy", "category": "policy", "tags": "refund,service"},
        )
        self.assertEqual(upload.status_code, 202, upload.text)
        doc_id = upload.json()["doc_id"]
        self.assertEqual(upload.json()["status"], "pending")

        document_service.process_knowledge_document(doc_id)
        listed = self.client.get("/knowledge/documents", headers=self.headers)
        self.assertEqual(listed.status_code, 200)
        document = next(item for item in listed.json() if item["doc_id"] == doc_id)
        self.assertEqual(document["status"], "ready")
        self.assertEqual(document["chunk_count"], 1)
        db = SessionLocal()
        try:
            parent = DatabaseManager(db).get_knowledge_parent(doc_id)
            self.assertIsNotNone(parent)
            self.assertIn("# Policy", parent.content)
        finally:
            db.close()

        chunks = self.client.get(
            f"/knowledge/documents/{doc_id}/chunks", headers=self.headers
        )
        self.assertEqual(chunks.status_code, 200)
        self.assertEqual(chunks.json()[0]["section"], "Refund")

        retry = self.client.post(
            f"/knowledge/documents/{doc_id}/retry", headers=self.headers
        )
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(retry.json()["status"], "pending")

        deleted = self.client.delete(
            f"/knowledge/documents/{doc_id}", headers=self.headers
        )
        self.assertEqual(deleted.status_code, 200)
        self.assertFalse(list((_root / "uploads").glob("*")))

    def test_change_password_keeps_current_session_and_revokes_others(self):
        email = "profile@example.com"
        old_password = "old-password-123"
        new_password = "new-password-456"
        registered = self.client.post(
            "/auth/register", json={"email": email, "password": old_password}
        )
        self.assertEqual(registered.status_code, 201, registered.text)
        current_token = registered.json()["token"]
        second_login = self.client.post(
            "/auth/login", json={"email": email, "password": old_password}
        )
        second_token = second_login.json()["token"]

        wrong = self.client.put(
            "/auth/password",
            headers={"Authorization": f"Bearer {current_token}"},
            json={"current_password": "wrong-password", "new_password": new_password},
        )
        self.assertEqual(wrong.status_code, 400)

        changed = self.client.put(
            "/auth/password",
            headers={"Authorization": f"Bearer {current_token}"},
            json={"current_password": old_password, "new_password": new_password},
        )
        self.assertEqual(changed.status_code, 200, changed.text)
        self.assertEqual(
            self.client.get(
                "/auth/me", headers={"Authorization": f"Bearer {current_token}"}
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(
                "/auth/me", headers={"Authorization": f"Bearer {second_token}"}
            ).status_code,
            401,
        )
        self.assertEqual(
            self.client.post(
                "/auth/login", json={"email": email, "password": old_password}
            ).status_code,
            401,
        )
        self.assertEqual(
            self.client.post(
                "/auth/login", json={"email": email, "password": new_password}
            ).status_code,
            200,
        )

    def test_rejects_non_md_files(self):
        for filename in (
            "notes.markdown", "notes.txt", "data.csv", "page.html",
            "manual.pdf", "policy.docx", "plans.xlsx",
        ):
            with self.subTest(filename=filename):
                response = self.client.post(
                    "/knowledge/documents",
                    headers=self.headers,
                    files={"file": (filename, b"not allowed", "application/octet-stream")},
                )
                self.assertEqual(response.status_code, 400)

    def test_upload_uses_first_h1_as_default_title(self):
        upload = self.client.post(
            "/knowledge/documents",
            headers=self.headers,
            files={"file": ("dx-maoxing.md", "# 电信猫星卡示例\n\n## 资费\n\n示例内容。".encode("utf-8"), "text/markdown")},
            data={"title": "", "category": "product", "tags": ""},
        )
        self.assertEqual(upload.status_code, 202, upload.text)
        self.assertEqual(upload.json()["title"], "电信猫星卡示例")
        doc_id = upload.json()["doc_id"]
        deleted = self.client.delete(
            f"/knowledge/documents/{doc_id}", headers=self.headers
        )
        self.assertEqual(deleted.status_code, 200)


if __name__ == "__main__":
    unittest.main()
