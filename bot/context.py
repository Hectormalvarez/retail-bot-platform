from __future__ import annotations

from dataclasses import dataclass, field

from api_client import ApiClient
from config import BotConfig


@dataclass
class BotContext:
    """Shared application context injected into bot_data at startup.

    Handlers access this via ``context.application.bot_data["ctx"]``
    so they never need to import a concrete ApiClient or Config directly.
    """

    config: BotConfig
    api: ApiClient
    # Future: add rate_limiter, db_pool, cache, etc. here
    extra: dict = field(default_factory=dict)
