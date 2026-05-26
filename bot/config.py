from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class BotConfig:
    """Centralised configuration loaded from the environment once at startup."""

    token: str
    api_base_url: str
    persistence_path: str = field(default="data/bot_state.pickle")
    log_level: str = field(default="INFO")
    data_dir: Path = field(default=Path("data"))

    @classmethod
    def from_env(cls) -> BotConfig:
        """Build config from environment variables (with sensible defaults)."""
        token = os.getenv("TELEGRAM_TOKEN")
        if not token:
            raise ValueError("TELEGRAM_TOKEN is not set")

        return cls(
            token=token,
            api_base_url=os.getenv("API_URL", "http://api:8000/api/"),
            persistence_path=os.getenv("BOT_PERSISTENCE_PATH", "data/bot_state.pickle"),
            log_level=os.getenv("BOT_LOG_LEVEL", "INFO"),
        )
