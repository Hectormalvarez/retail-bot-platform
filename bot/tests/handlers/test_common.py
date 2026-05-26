from unittest.mock import AsyncMock, MagicMock

import pytest

from handlers.common import back_to_start, clear_chat_footprint, start


# ---- pure helpers (no DI needed) ----------------------------------------


@pytest.mark.asyncio
async def test_clear_chat_footprint_deletes_stale_menu():
    update = MagicMock()
    update.message = None
    update.effective_chat.id = 12345

    context = MagicMock()
    context.user_data = {"active_menu_id": 999}
    context.bot.delete_message = AsyncMock()

    await clear_chat_footprint(update, context)

    context.bot.delete_message.assert_called_once_with(
        chat_id=12345, message_id=999
    )
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


@pytest.mark.asyncio
async def test_clear_chat_footprint_handles_delete_exception():
    """When delete_message raises, the exception is caught and logged."""
    update = MagicMock()
    update.message = None
    update.effective_chat.id = 12345

    context = MagicMock()
    context.user_data = {"active_menu_id": 999}
    context.bot.delete_message = AsyncMock(side_effect=Exception("not found"))

    await clear_chat_footprint(update, context)

    # Should not raise, and user_data should still be cleared
    assert context.user_data["active_menu_id"] is None


# ---- start / back_to_start (need app.bot_data["ctx"]) -------------------


@pytest.mark.asyncio
async def test_start_command_renders_menu(context_with_app):
    """start() syncs user and sends a welcome message."""
    context_with_app.user_data = {}

    update = MagicMock()
    update.effective_user.id = 123
    update.effective_user.username = "test_user"
    update.effective_user.first_name = "Test"
    update.effective_user.last_name = "User"
    update.effective_chat.send_message = AsyncMock()
    update.effective_chat.send_message.return_value.message_id = 404
    update.message = None

    await start(update, context_with_app)

    update.effective_chat.send_message.assert_called_once()
    assert context_with_app.user_data["active_menu_id"] == 404
    ctx = context_with_app.application.bot_data["ctx"]
    assert 123 in ctx.api.users


@pytest.mark.asyncio
async def test_back_to_start_edits_message():
    update = MagicMock()
    update.callback_query = AsyncMock()
    context = MagicMock()

    await back_to_start(update, context)

    update.callback_query.answer.assert_called_once()
    update.callback_query.edit_message_text.assert_called_once()

    call_args = update.callback_query.edit_message_text.call_args[1]
    assert "Welcome to the Retail Bot!" in call_args["text"]