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
            logger.info(f"API payload successfully retrieved: {len(data)} items found.")
            return data
        except httpx.HTTPError as exc:
            logger.error(f"API gateway connection failure: {exc}")
            return []
