import logging
import os

import httpx

logger = logging.getLogger(__name__)
API_BASE_URL = os.getenv("API_URL", "http://api:8000/api/")


async def fetch_products():
    """Fetches product catalog data over the network mesh."""
    logger.info("Dispatching API request to fetch products...")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{API_BASE_URL}products/")
            response.raise_for_status()
            data = response.json()
            logger.info(f"Retrieved {len(data)} items from catalog.")
            return data
        except httpx.HTTPError as exc:
            logger.error(f"API gateway connection failure: {exc}")
            return []


async def sync_user(user_data: dict):
    """Saves or updates a user profile instantly inside PostgreSQL."""
    tg_id = user_data["telegram_id"]
    async with httpx.AsyncClient() as client:
        try:
            url = f"{API_BASE_URL}users/{tg_id}/"
            res = await client.get(url)

            if res.status_code == 404:
                # User does not exist yet -> Create record
                post_res = await client.post(f"{API_BASE_URL}users/", json=user_data)
                post_res.raise_for_status()
                logger.info(f"Registered new shopper profile: {tg_id}")
            else:
                # User profile exists -> Patch any changes (e.g. updated username)
                patch_res = await client.patch(url, json=user_data)
                patch_res.raise_for_status()
                logger.info(f"Synchronized existing profile changes: {tg_id}")
        except httpx.HTTPError as exc:
            logger.error(f"Failed to sync user context {tg_id}: {exc}")


async def fetch_product_detail(product_id: int):
    """Fetches a single product's details from the DRF gateway."""
    logger.info(f"Fetching details for product ID: {product_id}")
    async with httpx.AsyncClient() as client:
        try:
            url = f"{API_BASE_URL}products/{product_id}/"
            response = await client.get(url)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            logger.error(f"Failed to fetch product {product_id}: {exc}")
            return None


async def fetch_user_cart(tg_id: int):
    """Retrieves the active cart layout for a specific Telegram user."""
    async with httpx.AsyncClient() as client:
        try:
            res = await client.get(f"{API_BASE_URL}carts/{tg_id}/")
            if res.status_code == 404:
                # Auto-initialize database-backed cart if missing
                create_res = await client.post(
                    f"{API_BASE_URL}carts/", json={"user": tg_id}
                )
                create_res.raise_for_status()
                res = await client.get(f"{API_BASE_URL}carts/{tg_id}/")
            res.raise_for_status()
            return res.json()
        except httpx.HTTPError as exc:
            logger.error(f"Cart synchronization error for {tg_id}: {exc}")
            return None


async def add_product_to_cart(tg_id: int, product_id: int):
    """Increments a product volume or builds a new item row entry."""
    cart = await fetch_user_cart(tg_id)
    if not cart:
        return False

    # Extract match to avoid unique tuple constraints violations
    existing_item = next((i for i in cart["items"] if i["product"] == product_id), None)

    async with httpx.AsyncClient() as client:
        try:
            if existing_item:
                url = f"{API_BASE_URL}cart-items/{existing_item['id']}/"
                payload = {"quantity": existing_item["quantity"] + 1}
                res = await client.patch(url, json=payload)
            else:
                url = f"{API_BASE_URL}cart-items/"
                payload = {
                    "cart": cart["id"],
                    "product": product_id,
                    "quantity": 1,
                }
                res = await client.post(url, json=payload)
            res.raise_for_status()
            return True
        except httpx.HTTPError as exc:
            logger.error(f"Failed to write cart item adjustment: {exc}")
            return False


async def update_item_quantity(item_id: int, new_qty: int):
    """Alters or deletes a cart item line row based on scale context."""
    async with httpx.AsyncClient() as client:
        try:
            url = f"{API_BASE_URL}cart-items/{item_id}/"
            if new_qty <= 0:
                res = await client.delete(url)
            else:
                res = await client.patch(url, json={"quantity": new_qty})
            res.raise_for_status()
            return True
        except httpx.HTTPError as exc:
            logger.error(f"Failed updating cart item {item_id}: {exc}")
            return False
