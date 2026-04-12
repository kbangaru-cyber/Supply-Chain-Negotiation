from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


load_dotenv()


class Settings(BaseSettings):
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(default="claude-3-5-haiku-latest", alias="ANTHROPIC_MODEL")
    langfuse_public_key: str | None = Field(default=None, alias="LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: str | None = Field(default=None, alias="LANGFUSE_SECRET_KEY")
    langfuse_base_url: str = Field(default="https://cloud.langfuse.com", alias="LANGFUSE_BASE_URL")
    base_price: float = Field(default=100.0, alias="PROVEAI_BASE_PRICE")
    noise_epsilon: float = Field(default=8.0, alias="PROVEAI_NOISE_EPSILON")
    manufacturer_margin: float = Field(default=12.0, alias="PROVEAI_MANUFACTURER_MARGIN")
    max_stage_turns: int = Field(default=6, alias="PROVEAI_MAX_STAGE_TURNS")
    runs_dir: Path = Path("runs")

    model_config = SettingsConfigDict(populate_by_name=True, extra="ignore")

