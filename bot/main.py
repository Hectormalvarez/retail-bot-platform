import logging
import os

from dotenv import load_dotenv
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from handlers import cart, catalog, checkout, common

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

    app.add_handler(CommandHandler("start", common.start))
    app.add_handler(CommandHandler("catalog", catalog.catalog_command))
    app.add_handler(CommandHandler("cart", cart.cart_command))

    checkout_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(checkout.start_checkout, pattern=r"^checkout$")
        ],
        states={
            checkout.WAITING_FOR_ADDRESS: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, checkout.capture_address
                )
            ],
            checkout.CONFIRMING: [
                CallbackQueryHandler(
                    checkout.finalize_order_placeholder,
                    pattern=r"^confirm_checkout$",
                ),
                CallbackQueryHandler(
                    checkout.cancel_checkout, pattern=r"^cancel_checkout$"
                ),
            ],
        },
        fallbacks=[CommandHandler("cancel", checkout.cancel_command_fallback)],
        allow_reentry=True,
    )
    app.add_handler(checkout_conv)

    app.add_handler(
        CallbackQueryHandler(catalog.view_product_detail, pattern=r"^view_prod_\d+$")
    )
    app.add_handler(
        CallbackQueryHandler(catalog.back_to_catalog, pattern=r"^back_catalog$")
    )
    app.add_handler(CallbackQueryHandler(common.back_to_start, pattern=r"^back_start$"))
    app.add_handler(CallbackQueryHandler(cart.cart_command, pattern=r"^view_cart_nav$"))
    app.add_handler(
        CallbackQueryHandler(cart.add_to_cart_handler, pattern=r"^add_to_cart_\d+$")
    )
    app.add_handler(
        CallbackQueryHandler(
            cart.adjust_quantity_handler, pattern=r"^qty_(up|down)_\d+_\d+$"
        )
    )

    logger.info("Initializing modular Telegram bot routing map...")
    app.run_polling()
