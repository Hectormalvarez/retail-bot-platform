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
