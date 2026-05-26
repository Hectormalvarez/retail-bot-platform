"""Shared fixtures for handler unit tests.

Uses ``MockApiClient`` so no network calls are ever made.
Handlers receive dependencies via ``app.bot_data["ctx"]``.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from telegram import Update
from telegram.ext import CallbackContext

from api_client import MockApiClient
from config import BotConfig
from context import BotContext


@pytest.fixture
def mock_api():
    """In-memory API client pre-loaded with sample data."""
    return MockApiClient(
        products=[
            {
                "id": 1,
                "name": "Test Product",
                "price": "19.99",
                "category_name": "Electronics",
                "stock": 10,
                "description": "A test product",
            },
        ],
        product_details={
            1: {
                "id": 1,
                "name": "Test Product",
                "price": "19.99",
                "category_name": "Electronics",
                "stock": 10,
                "description": "A test product",
            },
        },
    )


@pytest.fixture
def bot_config():
    return BotConfig(
        token="test-token",
        api_base_url="http://fake.local/api/",
    )


@pytest.fixture
def bot_context(mock_api, bot_config):
    return BotContext(config=bot_config, api=mock_api)


@pytest.fixture
def mock_update():
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock()
    update.effective_chat = MagicMock()
    update.callback_query = MagicMock()
    return update


@pytest.fixture
def mock_query(mock_update):
    return mock_update.callback_query


@pytest.fixture
def mock_context():
    context = MagicMock(spec=CallbackContext)
    context.user_data = {}
    context.bot = MagicMock()
    return context


@pytest.fixture
def app_with_context(bot_context):
    """A minimal ``Application`` surrogate with ``bot_data`` wired up.

    Because we only need ``context.application.bot_data["ctx"]`` to
    resolve, we build a fake application object instead of the real one.
    """
    app = MagicMock()
    app.bot_data = {"ctx": bot_context}
    return app


@pytest.fixture
def context_with_app(mock_context, app_with_context):
    """A ``CallbackContext`` (or mock) that carries a fake ``application``."""
    mock_context.application = app_with_context
    return mock_context