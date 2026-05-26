from __future__ import annotations

import pytest

from config import BotConfig


class TestBotConfig:
    def test_from_env_raises_without_token(self):
        """from_env() should raise ValueError when TELEGRAM_TOKEN is not set."""
        import os

        if "TELEGRAM_TOKEN" in os.environ:
            del os.environ["TELEGRAM_TOKEN"]
        with pytest.raises(ValueError, match="TELEGRAM_TOKEN"):
            BotConfig.from_env()

    def test_from_env_with_token(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_TOKEN", "test:token")
        monkeypatch.setenv("API_URL", "http://test/api/")
        config = BotConfig.from_env()
        assert config.token == "test:token"
        assert config.api_base_url == "http://test/api/"
        assert config.persistence_path == "data/bot_state.pickle"
