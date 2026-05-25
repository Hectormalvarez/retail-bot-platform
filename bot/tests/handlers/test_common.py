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


from handlers.common import start, back_to_start

@pytest.mark.asyncio
async def test_start_command_renders_menu(mocker):
    # Prevent network calls during the UI test
    mocker.patch("handlers.common.sync_user", new_callable=AsyncMock)
    mocker.patch("handlers.common.clear_chat_footprint", new_callable=AsyncMock)

    update = MagicMock()
    update.effective_user.id = 123
    update.effective_user.username = "test_user"
    update.effective_user.first_name = "Test"
    update.effective_user.last_name = "User"
    
    update.effective_chat.send_message = AsyncMock()
    update.effective_chat.send_message.return_value.message_id = 404

    context = MagicMock()
    context.user_data = {}

    await start(update, context)

    update.effective_chat.send_message.assert_called_once()
    assert context.user_data["active_menu_id"] == 404


@pytest.mark.asyncio
async def test_back_to_start_edits_message():
    update = MagicMock()
    update.callback_query = AsyncMock()
    context = MagicMock()

    await back_to_start(update, context)

    update.callback_query.answer.assert_called_once()
    update.callback_query.edit_message_text.assert_called_once()
    
    # Verify the text contains our welcome message
    call_args = update.callback_query.edit_message_text.call_args[1]
    assert "Welcome to the Retail Bot!" in call_args["text"]
