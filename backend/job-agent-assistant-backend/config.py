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
        return self.DATABASE_URL.replace("+asyncpg", "")

    # JWT（SECRET_KEY 必须在 .env 中显式配置，不设默认值防误用）
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440  # 24 小时

    # 代理（下载模型时使用）
    HTTP_PROXY: str = ""
    HTTPS_PROXY: str = ""

    # RAG / Embedding
    EMBEDDING_MODEL: str = "BAAI/bge-small-zh-v1.5"  # 首次运行自动下载 ~100MB
    EMBEDDING_DEVICE: str = "cpu"
    UPLOAD_DIR: str = "uploads/resumes"
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 50
    RETRIEVAL_TOP_K: int = 5
    RETRIEVAL_THRESHOLD: float = 0.55  # 余弦距离上限（<=> < 0.55 即相似度 > 0.45）

    # 应用
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    DEBUG: bool = False


settings = Settings()
