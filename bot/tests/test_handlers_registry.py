"""Test the handler auto-discovery in handlers/__init__.py."""

from __future__ import annotations

from unittest.mock import MagicMock

import handlers


def test_register_all_works_with_real_modules():
    """register_all runs through the real module list without error."""
    app = MagicMock()
    # Should not raise – all real modules have register_handlers()
    handlers.register_all(app)
    assert app.add_handler.call_count > 0