import logging
import os
import traceback

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, ApplicationBuilder, ContextTypes

from api_client import HttpApiClient
from config import BotConfig
from context import BotContext
from handlers import register_all

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def global_error_handler(
    update: Update | None, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Centralised fallback for unhandled runtime exceptions.

    Logs the full traceback securely and, when possible, sends a friendly
    message to the active chat so the user knows a minor refresh is needed.
    """
    traceback_str = "".join(
        traceback.format_exception(None, context.error, context.error.__traceback__)
    )
    logger.error(
        "Unhandled exception: %s\n%s",
        context.error,
        traceback_str,
    )

    if update is not None and update.effective_chat is not None:
        try:
            await update.effective_chat.send_message(
                "⚠️ A minor interface hiccup occurred. "
                "Please use /start to refresh the dashboard."
            )
        except Exception:
            logger.debug("Failed to send error notification to chat.")


def build_app(config: BotConfig | None = None) -> Application:
    """Assembles the bot application with DI context and auto-registered handlers.

    Parameters
    ----------
    config:
        Optional override – defaults to ``BotConfig.from_env()``.
    """
    if config is None:
        config = BotConfig.from_env()

    os.makedirs(config.data_dir, exist_ok=True)

    app = (
        ApplicationBuilder()
        .token(config.token)
        .build()
    )

    # Inject shared context so handlers never import a concrete class.
    ctx = BotContext(
        config=config,
        api=HttpApiClient(base_url=config.api_base_url),
    )
    app.bot_data["ctx"] = ctx

    # Auto-discover and register all handler modules.
    register_all(app)

    # Mount the global error handler last so it wraps everything.
    app.add_error_handler(global_error_handler)

    return app


if __name__ == "__main__":
    logger.info("Starting Retail Bot...")
    application = build_app()
    application.run_polling()
