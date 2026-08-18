"""Simple API key authentication for bot-to-API traffic."""

from __future__ import annotations

from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed


class APIKeyAuthentication(BaseAuthentication):
    """Authenticates requests via an ``X-API-Key`` header.

    This is a lightweight gate designed for server-to-server (bot → API)
    communication. It is *not* a substitute for proper user-level auth
    in end-user-facing scenarios.
    """

    def authenticate(self, request):
        api_key = request.headers.get("X-API-Key")
        if api_key is None:
            raise AuthenticationFailed("Missing API key.")
        if api_key != settings.API_KEY:
            raise AuthenticationFailed("Invalid API key.")
        # Authenticated but no user object — the bot acts on behalf of
        # Telegram users, not as a Django user.
        return (None, None)
