"""환경변수 기반 설정."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(REPO_ROOT / ".env"), extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def _ignore_blank_values(cls, values):
        """.env.example처럼 값이 비어 있는 항목은 미설정으로 보고 기본값을 사용한다."""
        if isinstance(values, dict):
            return {key: value for key, value in values.items() if not (isinstance(value, str) and value.strip() == "")}
        return values

    app_name: str = "YardGuard API"
    database_url: str = f"sqlite:///{REPO_ROOT / 'yardguard.db'}"
    data_dir: Path = REPO_ROOT / "data"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # LLM (없으면 결정론적 모의 어댑터로 대체)
    llm_provider: str | None = None
    llm_api_key: str | None = None
    llm_model: str = "claude-sonnet-5"
    llm_timeout_seconds: float = 20.0

    # 업로드 제한
    max_csv_bytes: int = 2 * 1024 * 1024
    max_csv_rows: int = 1000
    max_description_length: int = 2000

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def zones_path(self) -> Path:
        return self.data_dir / "zones.json"

    @property
    def rules_path(self) -> Path:
        return self.data_dir / "rules.json"

    @property
    def work_items_csv_path(self) -> Path:
        return self.data_dir / "work_items.csv"

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_provider and self.llm_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
