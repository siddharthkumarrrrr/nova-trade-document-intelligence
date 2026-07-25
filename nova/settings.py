from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """Filesystem and HTTP configuration resolved from one composition root."""

    root: Path
    host: str = "127.0.0.1"
    port: int = 8000
    max_upload_bytes: int = 20 * 1024 * 1024
    allowed_content_types: tuple[str, ...] = (
        "application/pdf",
        "image/png",
        "image/jpeg",
        "image/webp",
    )

    @property
    def env_path(self) -> Path:
        return self.root / ".env"

    @property
    def database_path(self) -> Path:
        return self.root / "data" / "nova.db"

    @property
    def checkpoint_path(self) -> Path:
        return self.root / "data" / "langgraph-checkpoints.db"

    @property
    def upload_path(self) -> Path:
        return self.root / "data" / "uploads"

    @property
    def rules_path(self) -> Path:
        return self.root / "config" / "customer_rules.json"

    @property
    def web_path(self) -> Path:
        return self.root / "web"


SETTINGS = Settings(root=Path(__file__).resolve().parents[1])

