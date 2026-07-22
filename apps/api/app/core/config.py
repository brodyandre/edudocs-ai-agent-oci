from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuração centralizada da API e do pipeline."""

    model_config = SettingsConfigDict(env_prefix="EDUDOCS_", env_file=".env", extra="ignore")

    root_dir: Path | None = None
    env: str = "development"
    manifest_path: Path = Path("../../corpus/manifest.json")
    documents_dir: Path = Path("../../corpus/documents")
    index_dir: Path = Path("../../corpus/index")
    embedding_provider: str = "fake"
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    fake_embedding_dimension: int = Field(default=32, ge=2, le=4096)
    chunk_size: int = Field(default=900, ge=120, le=8000)
    chunk_overlap: int = Field(default=120, ge=0, le=4000)
    batch_size: int = Field(default=16, ge=1, le=512)
    default_top_k: int = Field(default=5, ge=1, le=50)
    testing: bool = False
    llm_provider: str = Field(
        default="fake",
        validation_alias=AliasChoices("EDUDOCS_LLM_PROVIDER", "LLM_PROVIDER"),
    )
    groq_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("EDUDOCS_GROQ_API_KEY", "GROQ_API_KEY"),
    )
    groq_model: str = Field(
        default="llama-3.1-8b-instant",
        validation_alias=AliasChoices("EDUDOCS_GROQ_MODEL", "GROQ_MODEL"),
    )
    llm_temperature: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        validation_alias=AliasChoices("EDUDOCS_LLM_TEMPERATURE", "LLM_TEMPERATURE"),
    )
    llm_timeout_seconds: float = Field(
        default=20.0,
        ge=1.0,
        le=120.0,
        validation_alias=AliasChoices("EDUDOCS_LLM_TIMEOUT_SECONDS", "LLM_TIMEOUT_SECONDS"),
    )
    llm_max_retries: int = Field(
        default=1,
        ge=0,
        le=3,
        validation_alias=AliasChoices("EDUDOCS_LLM_MAX_RETRIES", "LLM_MAX_RETRIES"),
    )
    min_question_length: int = Field(default=3, ge=1, le=100)
    max_question_length: int = Field(default=800, ge=50, le=4000)
    chat_top_k: int = Field(default=6, ge=1, le=20)
    min_retrieval_score: float = Field(default=0.12, ge=0.0, le=1.0)
    evidence_limit: int = Field(default=5, ge=1, le=10)
    max_context_chars: int = Field(default=6000, ge=500, le=20000)
    max_retrieval_attempts: int = Field(default=2, ge=1, le=2)

    @field_validator("chunk_overlap")
    @classmethod
    def overlap_must_fit(cls, value: int, info: Any) -> int:
        chunk_size = info.data.get("chunk_size")
        if chunk_size is not None and value >= chunk_size:
            raise ValueError("chunk_overlap deve ser menor que chunk_size.")
        return value

    @property
    def repo_root(self) -> Path:
        if self.root_dir is not None:
            return self.root_dir.resolve()
        return Path(__file__).resolve().parents[4]

    @property
    def api_root(self) -> Path:
        return Path(__file__).resolve().parents[2]

    def resolve_repo_path(self, path: Path) -> Path:
        if path.is_absolute():
            resolved = path.resolve()
        else:
            repo_relative = (self.repo_root / path).resolve()
            if self.root_dir is not None:
                resolved = repo_relative
            else:
                api_relative = (self.api_root / path).resolve()
                resolved = (
                    api_relative
                    if api_relative.exists() or not repo_relative.exists()
                    else repo_relative
                )
        if not resolved.is_relative_to(self.repo_root):
            raise ValueError(f"Caminho fora do repositório: {path}")
        return resolved

    @property
    def resolved_manifest_path(self) -> Path:
        return self.resolve_repo_path(self.manifest_path)

    @property
    def resolved_documents_dir(self) -> Path:
        return self.resolve_repo_path(self.documents_dir)

    @property
    def resolved_index_dir(self) -> Path:
        return self.resolve_repo_path(self.index_dir)

    def index_config_fingerprint(self) -> str:
        payload = {
            "embedding_model": self.embedding_model,
            "embedding_provider": self.embedding_provider,
            "fake_embedding_dimension": self.fake_embedding_dimension,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "batch_size": self.batch_size,
        }
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


@lru_cache
def get_settings() -> Settings:
    return Settings()
