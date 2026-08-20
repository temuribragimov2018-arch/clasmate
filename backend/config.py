from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List


class Settings(BaseSettings):
    APP_NAME: str = "ClassMate"
    DEBUG: bool = False
    SECRET_KEY: str = "change-this-to-a-long-random-secret-key-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Railway автоматически подставляет DATABASE_URL из PostgreSQL плагина
    DATABASE_URL: str = "sqlite:///./classmate.db"

    CORS_ORIGINS: str = "*"

    MAX_UPLOAD_SIZE_MB: int = 50
    UPLOAD_DIR: str = "uploads"
    ALLOWED_IMAGE_TYPES: str = "image/jpeg,image/png,image/gif,image/webp"
    ALLOWED_DOCUMENT_TYPES: str = "application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain"

    PRO_DEFAULT_PRICE_30: int = 199
    PRO_DEFAULT_PRICE_90: int = 499
    PRO_DEFAULT_PRICE_365: int = 1499

    PAYMENT_DETAILS: str = "Сбербанк: 4276 XXXX XXXX XXXX\nПолучатель: Иван Иванов\nКомментарий: ClassMate PRO + ваш user_id"

    @property
    def cors_origins_list(self) -> List[str]:
        if self.CORS_ORIGINS.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    @property
    def allowed_image_types_list(self) -> List[str]:
        return [t.strip() for t in self.ALLOWED_IMAGE_TYPES.split(",") if t.strip()]

    @property
    def allowed_document_types_list(self) -> List[str]:
        return [t.strip() for t in self.ALLOWED_DOCUMENT_TYPES.split(",") if t.strip()]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
