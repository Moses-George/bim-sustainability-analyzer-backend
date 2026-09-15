from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = ""
    CLOUDINARY_URL: str | None = None
    SECRET_KEY: str = ""
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"
    USE_CELERY: bool = False
    UPLOAD_DIR: str = "/tmp/bim-uploads"
    EPW_FILE: str | None = None
    CORS_ORIGINS: str = "*"

    # Real LLM streaming chat (falls back to canned hints if unset)
    DEEPSEEK_API_KEY: str | None = None
    DEEPSEEK_MODEL: str = "deepseek-chat"
    
    OPENROUTER_API_KEY: str | None = None
    OPENROUTER_MODEL: str = "inclusionai/ling-3.0-flash-vl:free"  # Free OpenAI model on OpenRoute

    class Config:
        env_file = ".env"


settings = Settings()
