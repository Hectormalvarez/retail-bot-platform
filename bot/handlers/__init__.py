"""Handler auto-discovery and registration.

Each handler module should export a ``register_handlers(app)`` function.
The ``register_all()`` function discovers all such modules and calls their
register function in a deterministic order.

Adding a new feature:
    1. Create ``handlers/my_feature.py``
    2. Define ``register_handlers(app)`` in it
    3. Done — no edits to ``main.py`` required.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from telegram.ext import Application

logger = logging.getLogger(__name__)

# Ordered list of modules to register.
# Modules that declare ConversationHandler entries that depend on other
# modules' callbacks should be listed *after* those dependencies.
_HANDLER_MODULES = [
    "handlers.common",
    "handlers.catalog",
    "handlers.cart",
    "handlers.checkout",
]


def register_all(app: Application) -> None:
    """Import and call ``register_handlers(app)`` for each known module."""
    for mod_name in _HANDLER_MODULES:
        try:
            mod = __import__(mod_name, fromlist=["register_handlers"])
            if hasattr(mod, "register_handlers"):
                mod.register_handlers(app)
                logger.info("Registered handlers from %s", mod_name)
            else:
                logger.warning(
                    "Module %s has no register_handlers() — skipping", mod_name
                )
        except Exception:
            logger.exception("Failed to load handlers from %s", mod_name)
