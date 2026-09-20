from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录：config.py 所在目录。
# .env 用绝对路径加载：相对路径按进程 CWD 解析，从其他目录启动时会找不到 .env，
# 导致 key 全空，Embedding 请求构造出非法 header（Illegal header value b'Bearer '），
# 进而走进 get_responses 的兜底分支返回「遇到技术问题」。
BASE_DIR = Path(__file__).resolve().parent


# 从环境变量读取值
class Settings(BaseSettings):
    """Application settings and configuration."""
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        case_sensitive=False,
    )
    # DeepSeek Configuration (OpenAI-compatible API)
    deepseek_api_key: str = ""
    openai_api_base: str = "https://api.deepseek.com"

    # Database Configuration
    database_url: str = "sqlite:///./customer_support.db"

    # Vector Database Configuration
    chroma_db_path: str = "./chroma_db"
    knowledge_upload_path: str = "./knowledge_uploads"
    knowledge_upload_max_mb: int = 20
    # 硅基流动（SiliconFlow）OpenAI 兼容 Embedding，免本地模型下载
    siliconflow_api_key: str = ""               # https://cloud.siliconflow.cn 获取
    embedding_api_base: str = "https://api.siliconflow.cn/v1"
    embedding_api_key: str = ""                 # 留空则回退用 siliconflow_api_key
    embedding_model: str = "BAAI/bge-large-zh-v1.5"
    # RAG 切分与 MMR 检索参数（字符数，适合中英文混合客服资料）
    rag_child_chunk_size: int = 400
    rag_child_chunk_overlap: int = 60
    rag_fetch_k: int = 30
    rag_mmr_lambda: float = 0.7
    rag_hybrid_enabled: bool = True
    rag_lexical_weight: float = 0.35
    rag_rrf_k: int = 60
    # 是否在知识库初始化时种演示数据（默认关闭；生产只保留 product 产品知识）
    seed_demo_data: bool = False
    # Local directory where the embedding model is downloaded/stored（本地 BGE 方案备用）
    model_path: str = "./model"

    # Application Configuration
    debug: bool = True
    host: str = "localhost"
    port: int = 8000

    # Optional: Anthropic API
    anthropic_api_key: Optional[str] = None

    # Model Configuration
    model_name: str = "deepseek-v4-flash"
    temperature: float = 0.7
    max_tokens: int = 1000

# Global settings instance
settings = Settings()

# 数据库 / 向量库相对路径锚定到项目根目录：从其他目录启动时不应漂移到 CWD。
# .env 里写的是 ./customer_support.db 与 ./chroma_db，此处统一归一化为绝对路径。
if settings.database_url.startswith("sqlite:///./"):
    settings.database_url = "sqlite:///" + (BASE_DIR / settings.database_url[len("sqlite:///./"):]).as_posix()
if not Path(settings.chroma_db_path).is_absolute():
    settings.chroma_db_path = str(BASE_DIR / settings.chroma_db_path)
if not Path(settings.knowledge_upload_path).is_absolute():
    settings.knowledge_upload_path = str(BASE_DIR / settings.knowledge_upload_path)
