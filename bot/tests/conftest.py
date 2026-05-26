from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_update():
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_chat = MagicMock()
    update.callback_query = AsyncMock()
    return update


@pytest.fixture
def mock_query(mock_update):
    return mock_update.callback_query


@pytest.fixture
def mock_context():
    context = MagicMock()
    context.user_data = {}
    context.bot = MagicMock()
    return context
