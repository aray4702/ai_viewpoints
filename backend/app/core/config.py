from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    data_dir: Path = BACKEND_DIR / "data"
    database_url: str = ""  # defaults to sqlite file in data_dir
    queue_path: str = ""  # huey sqlite queue file

    anthropic_api_key: str = ""
    triage_model: str = "claude-haiku-4-5"
    extract_model: str = "claude-sonnet-5-5"
    extract_effort: str = "medium"  # low | medium | high

    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"

    voyage_api_key: str = ""
    embedding_model: str = "voyage-3"
    embedding_dim: int = 1024

    dedup_similarity: float = 0.90
    dedup_window_days: int = 90
    # whole transcripts fit in context; refuse (don't truncate) anything past this
    max_input_chars: int = 2_000_000
    quote_match_threshold: float = 90.0  # rapidfuzz partial_ratio

    # web / auth
    secret_key: str = "dev-insecure-change-me"
    web_base_url: str = "http://localhost:3000"  # links in emails and OAuth redirects
    admin_emails: list[str] = []
    session_days: int = 30

    discord_client_id: str = ""
    discord_client_secret: str = ""

    resend_api_key: str = ""  # without it, emails are logged instead of sent
    email_from: str = "Their Take <noreply@example.com>"

    @property
    def db_url(self) -> str:
        return self.database_url or f"sqlite:///{self.data_dir / 'viewpoints.db'}"

    @property
    def queue_file(self) -> str:
        return self.queue_path or str(self.data_dir / "queue.db")


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.data_dir.mkdir(parents=True, exist_ok=True)
    return s
