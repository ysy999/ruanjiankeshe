from pathlib import Path
from typing import Annotated, Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "ruanjiankeshe"
    DATABASE_URL: str
    # Legacy shared key retained so existing local .env files keep working.
    DASHSCOPE_API_KEY: str = ""
    LLM_PROVIDER: str = "deepseek"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "deepseek-flash"
    LLM_BASE_URL: str = "https://api.deepseek.com"
    EMBEDDING_PROVIDER: str = "dashscope"
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    EMBEDDING_MODEL: str = "text-embedding-v4"
    EMBEDDING_DIM: int = 1024
    MILVUS_HOST: str = "127.0.0.1"
    MILVUS_PORT: int = 19530
    CORS_ORIGINS: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173"]
    )
    WEB_SOURCES: Annotated[list[str], NoDecode] = Field(default_factory=list)

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> list[str]:
        if value is None or value == "":
            return ["http://localhost:5173"]
        if isinstance(value, str):
            text = value.strip()
            if text.startswith("["):
                import json

                parsed = json.loads(text)
                if isinstance(parsed, list):
                    return [str(item).strip() for item in parsed if str(item).strip()]
            return [item.strip() for item in text.split(",") if item.strip()]
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return [str(value)]

    @field_validator("WEB_SOURCES", mode="before")
    @classmethod
    def parse_web_sources(cls, value: Any) -> list[str]:
        if value is None or value == "":
            return []
        if isinstance(value, str):
            text = value.strip()
            if text.startswith("["):
                import json

                parsed = json.loads(text)
                if isinstance(parsed, list):
                    return [str(item).strip() for item in parsed if str(item).strip()]
            return [item.strip() for item in text.split(",") if item.strip()]
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return [str(value)]


settings = Settings()
