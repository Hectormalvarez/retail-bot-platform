from unittest.mock import AsyncMock, MagicMock

import pytest

from handlers.common import clear_chat_footprint


@pytest.mark.asyncio
async def test_clear_chat_footprint_deletes_stale_menu():
    update = MagicMock()
    update.message = None
    update.effective_chat.id = 12345

    context = MagicMock()
    context.user_data = {"active_menu_id": 999}
    context.bot.delete_message = AsyncMock()

    await clear_chat_footprint(update, context)

    context.bot.delete_message.assert_called_once_with(chat_id=12345, message_id=999)
    assert context.user_data["active_menu_id"] is None


@pytest.mark.asyncio
async def test_clear_chat_footprint_ignores_missing_menu():
    update = MagicMock()
    update.message = None

    context = MagicMock()
    context.user_data = {}
    context.bot.delete_message = AsyncMock()

    await clear_chat_footprint(update, context)

    context.bot.delete_message.assert_not_called()
