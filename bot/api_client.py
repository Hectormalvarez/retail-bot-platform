from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Interface (Protocol / ABC) – allows swapping HTTP for mocks in tests
# ---------------------------------------------------------------------------


class ApiClient(ABC):
    """Abstract interface for the DRF backend API client."""

    @abstractmethod
    async def fetch_products(
        self, category_id: int | None = None
    ) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def fetch_categories(self) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def sync_user(self, user_data: dict[str, Any]) -> None: ...

    @abstractmethod
    async def fetch_product_detail(self, product_id: int) -> dict[str, Any] | None: ...

    @abstractmethod
    async def fetch_user_cart(self, tg_id: int) -> dict[str, Any] | None: ...

    @abstractmethod
    async def add_product_to_cart(self, tg_id: int, product_id: int) -> bool: ...

    @abstractmethod
    async def update_item_quantity(self, item_id: int, new_qty: int) -> bool: ...

    @abstractmethod
    async def submit_order(
        self, tg_id: int, shipping_address: str
    ) -> dict[str, Any] | None: ...

    @abstractmethod
    async def fetch_addresses(self, tg_id: int) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def create_address(
        self, tg_id: int, label: str, full_address: str
    ) -> dict[str, Any] | None: ...

    @abstractmethod
    async def delete_address(self, address_id: int) -> bool: ...

    @abstractmethod
    async def fetch_user_orders(self, tg_id: int) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def fetch_store_config(self) -> dict[str, str]: ...


# ---------------------------------------------------------------------------
# Concrete HTTP implementation
# ---------------------------------------------------------------------------


class HttpApiClient(ApiClient):
    """Production client that talks to the Django REST API over httpx."""

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base_url = base_url.rstrip("/") + "/"
        self._api_key = api_key

    # ---- helpers ---------------------------------------------------------

    def _url(self, path: str) -> str:
        return f"{self._base_url}{path.lstrip('/')}"

    def _headers(self) -> dict[str, str]:
        if self._api_key:
            return {"X-API-Key": self._api_key}
        return {}

    async def _get(
        self, path: str, **kwargs: Any
    ) -> dict[str, Any] | list[dict[str, Any]] | None:
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(
                    self._url(path), headers=self._headers(), **kwargs
                )
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPError as exc:
                logger.error("GET %s failed: %s", path, exc)
                return None

    async def _post(
        self, path: str, json: dict[str, Any] | None = None, **kwargs: Any
    ) -> dict[str, Any] | None:
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(
                    self._url(path), json=json, headers=self._headers(), **kwargs
                )
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPError as exc:
                logger.error("POST %s failed: %s", path, exc)
                return None

    async def _patch(
        self, path: str, json: dict[str, Any] | None = None, **kwargs: Any
    ) -> dict[str, Any] | None:
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.patch(
                    self._url(path), json=json, headers=self._headers(), **kwargs
                )
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPError as exc:
                logger.error("PATCH %s failed: %s", path, exc)
                return None

    async def _delete(self, path: str, **kwargs: Any) -> bool:
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.delete(
                    self._url(path), headers=self._headers(), **kwargs
                )
                resp.raise_for_status()
                return True
            except httpx.HTTPError as exc:
                logger.error("DELETE %s failed: %s", path, exc)
                return False

    # ---- domain methods --------------------------------------------------

    async def fetch_products(
        self, category_id: int | None = None
    ) -> list[dict[str, Any]]:
        path = f"products/?category={category_id}" if category_id else "products/"
        data = await self._get(path)
        return data if isinstance(data, list) else []

    async def fetch_categories(self) -> list[dict[str, Any]]:
        data = await self._get("categories/")
        return data if isinstance(data, list) else []

    async def sync_user(self, user_data: dict[str, Any]) -> None:
        tg_id = user_data["telegram_id"]
        existing = await self._get(f"users/{tg_id}/")
        if existing is None:
            await self._post("users/", json=user_data)
            logger.info("Registered new shopper profile: %s", tg_id)
        else:
            await self._patch(f"users/{tg_id}/", json=user_data)
            logger.info("Synchronized existing profile: %s", tg_id)

    async def fetch_product_detail(self, product_id: int) -> dict[str, Any] | None:
        data = await self._get(f"products/{product_id}/")
        return data if isinstance(data, dict) else None

    async def fetch_user_cart(self, tg_id: int) -> dict[str, Any] | None:
        data = await self._get(f"carts/{tg_id}/")
        if data is not None:
            return data if isinstance(data, dict) else None
        # Auto-create a cart on first access
        created = await self._post("carts/", json={"user": tg_id})
        if created is None:
            return None
        data = await self._get(f"carts/{tg_id}/")
        return data if isinstance(data, dict) else None

    async def add_product_to_cart(self, tg_id: int, product_id: int) -> bool:
        cart = await self.fetch_user_cart(tg_id)
        if not cart:
            return False

        result = await self._post(
            "cart-items/",
            json={
                "cart": cart["id"],
                "product": product_id,
                "quantity": 1,
            },
        )
        return result is not None

    async def update_item_quantity(self, item_id: int, new_qty: int) -> bool:
        if new_qty <= 0:
            return await self._delete(f"cart-items/{item_id}/")
        result = await self._patch(f"cart-items/{item_id}/", json={"quantity": new_qty})
        return result is not None

    async def submit_order(
        self, tg_id: int, shipping_address: str
    ) -> dict[str, Any] | None:
        result = await self._post(
            "orders/",
            json={"user": tg_id, "shipping_address": shipping_address},
        )
        return result if isinstance(result, dict) else None

    async def fetch_addresses(self, tg_id: int) -> list[dict[str, Any]]:
        data = await self._get(f"addresses/?user={tg_id}")
        return data if isinstance(data, list) else []

    async def create_address(
        self, tg_id: int, label: str, full_address: str
    ) -> dict[str, Any] | None:
        result = await self._post(
            "addresses/",
            json={"user": tg_id, "label": label, "full_address": full_address},
        )
        return result if isinstance(result, dict) else None

    async def delete_address(self, address_id: int) -> bool:
        return await self._delete(f"addresses/{address_id}/")

    async def fetch_user_orders(self, tg_id: int) -> list[dict[str, Any]]:
        data = await self._get(f"orders/?user={tg_id}")
        return data if isinstance(data, list) else []

    async def fetch_store_config(self) -> dict[str, str]:
        data = await self._get("config/")
        if isinstance(data, dict):
            return data
        return {
            "venmo_handle": "@Fallback",
            "zelle_email": "fallback@local",
            "payment_instructions": "Please contact admin to pay.",
        }


# ---------------------------------------------------------------------------
# In-memory mock for unit tests
# ---------------------------------------------------------------------------


@dataclass
class MockApiClient(ApiClient):
    """Fake in-memory client – no network calls, ideal for handler tests."""

    products: list[dict] = None  # type: ignore[assignment]
    product_details: dict[int, dict] = None  # type: ignore[assignment]
    carts: dict[int, dict] = None  # type: ignore[assignment]
    users: set[int] = None  # type: ignore[assignment]
    categories: list[dict] = None  # type: ignore[assignment]
    next_cart_item_id: int = 1
    next_order_id: int = 1
    _addresses: list[dict] = None  # type: ignore[assignment]
    _next_address_id: int = 1
    _orders: list[dict] = None  # type: ignore[assignment]
    _config: dict[str, str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.products is None:
            self.products = []
        if self.categories is None:
            self.categories = []
        if self.product_details is None:
            self.product_details = {}
        if self.carts is None:
            self.carts = {}
        if self.users is None:
            self.users = set()
        if self._addresses is None:
            self._addresses = []
        if self._orders is None:
            self._orders = []
        if self._config is None:
            self._config = {
                "venmo_handle": "@TestVenmo",
                "zelle_email": "test@zelle.local",
                "payment_instructions": (
                    "Send money to {venmo_handle} or {zelle_email} with note {order_id}"
                ),
            }

    async def fetch_products(self, category_id: int | None = None) -> list[dict]:
        if category_id is not None:
            return [p for p in self.products if p.get("category") == category_id]
        return self.products

    async def fetch_categories(self) -> list[dict]:
        return self.categories

    async def sync_user(self, user_data: dict) -> None:
        self.users.add(user_data["telegram_id"])

    async def fetch_product_detail(self, product_id: int) -> dict | None:
        return self.product_details.get(product_id)

    async def fetch_user_cart(self, tg_id: int) -> dict | None:
        cart = self.carts.get(tg_id)
        if cart is None:
            # auto-create
            cart = {"id": tg_id, "items": [], "cart_total": "0.00"}
            self.carts[tg_id] = cart
        return cart

    async def add_product_to_cart(self, tg_id: int, product_id: int) -> bool:
        cart = await self.fetch_user_cart(tg_id)
        if not cart:
            return False
        detail = self.product_details.get(product_id, {})
        unit_price = float(detail.get("price", 0))

        existing = next((i for i in cart["items"] if i["product"] == product_id), None)
        if existing:
            existing["quantity"] += 1
            existing["subtotal"] = f"{unit_price * existing['quantity']:.2f}"
        else:
            cart["items"].append(
                {
                    "id": self.next_cart_item_id,
                    "product": product_id,
                    "product_name": detail.get("name", "Unknown"),
                    "quantity": 1,
                    "subtotal": f"{unit_price:.2f}",
                }
            )
            self.next_cart_item_id += 1
        cart["cart_total"] = f"{sum(float(i['subtotal']) for i in cart['items']):.2f}"
        return True

    async def update_item_quantity(self, item_id: int, new_qty: int) -> bool:
        for cart in self.carts.values():
            for item in cart["items"]:
                if item["id"] == item_id:
                    if new_qty <= 0:
                        cart["items"].remove(item)
                    else:
                        item["quantity"] = new_qty
                        unit_price = float(
                            self.product_details.get(item["product"], {}).get(
                                "price", 0
                            )
                        )
                        item["subtotal"] = f"{unit_price * new_qty:.2f}"
                    cart_total = sum(float(i["subtotal"]) for i in cart["items"])
                    cart["cart_total"] = f"{cart_total:.2f}"
                    return True
        return False

    async def submit_order(self, tg_id: int, shipping_address: str) -> dict | None:
        cart = self.carts.get(tg_id)
        if not cart or not cart["items"]:
            return None
        order = {
            "id": self.next_order_id,
            "user": tg_id,
            "total_amount": cart["cart_total"],
            "status": "PENDING",
            "shipping_address": shipping_address,
            "items": [
                {
                    "product_name": i["product_name"],
                    "quantity": i["quantity"],
                    "price_at_purchase": self.product_details.get(i["product"], {}).get(
                        "price", "0.00"
                    ),
                }
                for i in cart["items"]
            ],
        }
        self.next_order_id += 1
        self._orders.append(order)
        cart["items"].clear()
        cart["cart_total"] = "0.00"
        return order

    async def fetch_user_orders(self, tg_id: int) -> list[dict]:
        return [o for o in self._orders if o["user"] == tg_id]

    async def fetch_addresses(self, tg_id: int) -> list[dict]:
        return [a for a in self._addresses if a["user"] == tg_id]

    async def create_address(
        self, tg_id: int, label: str, full_address: str
    ) -> dict | None:
        addr = {
            "id": self._next_address_id,
            "user": tg_id,
            "label": label,
            "full_address": full_address,
        }
        self._next_address_id += 1
        self._addresses.append(addr)
        return addr

    async def delete_address(self, address_id: int) -> bool:
        for a in self._addresses:
            if a["id"] == address_id:
                self._addresses.remove(a)
                return True
        return False

    async def fetch_store_config(self) -> dict[str, str]:
        return self._config
