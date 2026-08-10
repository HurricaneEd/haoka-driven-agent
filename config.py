from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


# 从环境变量读取值
class Settings(BaseSettings):
    """Application settings and configuration."""
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
    )
    # DeepSeek Configuration (OpenAI-compatible API)
    deepseek_api_key: str = ""
    openai_api_base: str = "https://api.deepseek.com"

    # Database Configuration
    database_url: str = "sqlite:///./customer_support.db"

    # Vector Database Configuration
    chroma_db_path: str = "./chroma_db"
    # 硅基流动（SiliconFlow）OpenAI 兼容 Embedding，免本地模型下载
    siliconflow_api_key: str = ""               # https://cloud.siliconflow.cn 获取
    embedding_api_base: str = "https://api.siliconflow.cn/v1"
    embedding_api_key: str = ""                 # 留空则回退用 siliconflow_api_key
    embedding_model: str = "BAAI/bge-large-zh-v1.5"
    # 是否在知识库初始化时种演示数据（默认关闭；生产只保留 product 产品知识）
    seed_demo_data: bool = False
    # Local directory where the embedding model is downloaded/stored（本地 BGE 方案备用）
    model_path: str = "./model"

    # Application Configuration
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000

    # Optional: Anthropic API
    anthropic_api_key: Optional[str] = None

    # Model Configuration
    model_name: str = "deepseek-v4-flash"
    temperature: float = 0.7
    max_tokens: int = 1000

# Global settings instance
settings = Settings()
