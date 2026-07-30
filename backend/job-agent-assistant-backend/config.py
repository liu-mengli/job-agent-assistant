from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def _validate_secrets(self):
        """关键密钥不允许为空，防止 .env 缺失字段时静默降级"""
        if not self.JWT_SECRET_KEY:
            raise ValueError(
                "JWT_SECRET_KEY 未配置，请在 .env 文件中设置一个随机字符串。"
                "示例: JWT_SECRET_KEY=$(openssl rand -hex 32)"
            )
        if not self.DEEPSEEK_API_KEY:
            raise ValueError(
                "DEEPSEEK_API_KEY 未配置，请在 .env 文件中设置你的 DeepSeek API Key。"
            )
        return self

    # DeepSeek API
    DEEPSEEK_API_KEY: str
    DEEPSEEK_BASE_URL: str
    DEEPSEEK_MODEL: str

    # 数据库
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "job_agent"
    DB_USER: str = "postgres"
    DB_PASSWORD: str = ""

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @property
    def PG_URL(self) -> str:
        """psycopg 兼容格式（去掉 +asyncpg），供 AsyncPostgresSaver 使用"""
        base = self.DATABASE_URL.replace("+asyncpg", "")
        # 加 connect_timeout 防止数据库不可达时无限挂起
        if "?" in base:
            return f"{base}&connect_timeout=5"
        return f"{base}?connect_timeout=5"

    # JWT（SECRET_KEY 必须在 .env 中显式配置，不设默认值防误用）
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440  # 24 小时

    # 代理（下载模型时使用）
    HTTP_PROXY: str = ""
    HTTPS_PROXY: str = ""

    # CORS 允许的前端来源（逗号分隔，Docker 部署时通过环境变量覆盖）
    CORS_ORIGINS: str = "http://localhost:5173"

    # HuggingFace 缓存目录
    HF_HOME: str = "/app/models/huggingface"
    # HuggingFace 镜像端点（国内网络推荐 https://hf-mirror.com）
    HF_ENDPOINT: str = ""

    # RAG / Embedding（简历 RAG — bge-small-zh-v1.5, 512 维）
    EMBEDDING_MODEL: str = "BAAI/bge-small-zh-v1.5"  # 首次运行自动下载 ~100MB
    EMBEDDING_DEVICE: str = "cpu"
    UPLOAD_DIR: str = "uploads/resumes"
    RESUME_DIR: str = "uploads/resume"  # 简历展示静态资源目录
    RESUME_PDF_NAME: str = "附件简历_王文韬_Agent应用开发_四年经验.pdf"  # 简历 PDF 文件名（可改）
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 50
    RETRIEVAL_TOP_K: int = 5
    RETRIEVAL_THRESHOLD: float = 0.55  # 余弦距离上限（<=> < 0.55 即相似度 > 0.45）

    # 知识库 RAG（bge-m3, 1024 维，独立管线）
    KB_EMBEDDING_MODEL: str = "BAAI/bge-m3"
    KB_EMBEDDING_DEVICE: str = "cpu"
    KB_UPLOAD_DIR: str = "uploads/knowledge"
    KB_CHUNK_SIZE: int = 800
    KB_CHUNK_OVERLAP: int = 80
    KB_RETRIEVAL_TOP_K: int = 5
    KB_RETRIEVAL_THRESHOLD: float = 0.55
    KB_RERANKER_MODEL: str = "BAAI/bge-reranker-v2-m3"
    KB_RERANK_CANDIDATES: int = 20
    KB_RERANK_THRESHOLD: float = 0.01  # Cross-Encoder 精排分数门槛（评估验证最优值，Precision@5 从 0.36→0.74）
    KB_BM25_TOP_K: int = 10  # BM25 关键词检索返回条数，与 Dense 结果做 RRF 融合
    LIBREOFFICE_PATH: str = "/usr/bin/soffice"
    HR_RESUME_PATH: str = "uploads/简历.md"

    # 应用
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    DEBUG: bool = False


settings = Settings()
