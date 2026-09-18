"""Embedding 提供方适配。"""

from typing import List

import httpx
from langchain_core.embeddings import Embeddings


class SiliconFlowEmbeddings(Embeddings):
    def __init__(self, api_key: str, model: str, base_url: str):
        if not api_key:
            raise ValueError("未配置 EMBEDDING_API_KEY 或 SILICONFLOW_API_KEY")
        self.model = model
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=60.0,
        )

    def _embed(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        response = self._client.post("/embeddings", json={"model": self.model, "input": texts})
        if response.status_code != 200:
            raise RuntimeError(
                f"Embedding API error {response.status_code}: {response.text[:200]}"
            )
        data = sorted(response.json()["data"], key=lambda item: item.get("index", 0))
        return [item["embedding"] for item in data]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self._embed(texts)

    def embed_query(self, text: str) -> List[float]:
        return self._embed([text])[0]

