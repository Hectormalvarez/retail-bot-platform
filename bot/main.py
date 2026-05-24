import logging
import os

from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler

from handlers import catalog, common

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_TOKEN not set in .env")

    app = ApplicationBuilder().token(token).build()

    # Commands Registered via package modules
    app.add_handler(CommandHandler("start", common.start))
    app.add_handler(CommandHandler("catalog", catalog.catalog_command))

    # Pattern-matched callback routing via framework layer
    app.add_handler(
        CallbackQueryHandler(catalog.view_product_detail, pattern=r"^view_prod_\d+$")
    )
    app.add_handler(
        CallbackQueryHandler(catalog.back_to_catalog, pattern=r"^back_catalog$")
    )

    logger.info("Initializing modular Telegram bot routing map...")
    app.run_polling()
