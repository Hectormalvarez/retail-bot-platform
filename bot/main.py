import logging
import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from api_client import fetch_products

load_dotenv()

# Setup explicit container terminal formatting
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f"User {user.id} ({user.username}) initiated /start")
    text = "Welcome to the Retail Bot! Use /catalog to view active items."
    await update.message.reply_text(text)


async def catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Queries the API container and renders interactive menus."""
    user = update.effective_user
    logger.info(f"User {user.id} requested product catalog view.")

    products = await fetch_products()

    if not products:
        text = "The catalog is currently empty or down for maintenance."
        await update.message.reply_text(text)
        return

    keyboard = []
    for item in products:
        button_text = f"{item['name']} — ${item['price']}"
        callback_data = f"view_prod_{item['id']}"
        keyboard.append(
            [InlineKeyboardButton(button_text, callback_data=callback_data)]
        )

    reply_markup = InlineKeyboardMarkup(keyboard)
    menu_text = "📦 *Available Products*:\nSelect an item to view details:"
    await update.message.reply_text(
        text=menu_text, parse_mode="Markdown", reply_markup=reply_markup
    )


if __name__ == "__main__":
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_TOKEN not set in .env")

    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("catalog", catalog))

    logger.info("Initializing Telegram polling polling interface...")
    app.run_polling()
