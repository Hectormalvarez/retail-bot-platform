import logging
import os

from dotenv import load_dotenv
from telegram.ext import Application, ApplicationBuilder

from config import BotConfig
from context import BotContext
from handlers import register_all
from api_client import HttpApiClient

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


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

    return app


if __name__ == "__main__":
    logger.info("Starting Retail Bot...")
    application = build_app()
    application.run_polling()