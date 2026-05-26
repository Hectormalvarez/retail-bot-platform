"""Tests for the API client interface and its implementations."""

from __future__ import annotations

import httpx
import pytest

from api_client import HttpApiClient, MockApiClient


# ---------------------------------------------------------------------------
# MockApiClient (in-memory) – integration-like without a network
# ---------------------------------------------------------------------------


class TestMockApiClient:
    """Verify the in-memory client behaves like the real one."""

    @pytest.fixture
    def client(self) -> MockApiClient:
        return MockApiClient(
            products=[{"id": 1, "name": "T-Shirt", "price": "25.00"}],
            product_details={
                1: {
                    "id": 1,
                    "name": "T-Shirt",
                    "price": "25.00",
                    "category_name": "Gear",
                    "stock": 10,
                    "description": "A tee.",
                }
            },
        )

    @pytest.mark.asyncio
    async def test_fetch_products(self, client):
        result = await client.fetch_products()
        assert len(result) == 1
        assert result[0]["name"] == "T-Shirt"

    @pytest.mark.asyncio
    async def test_fetch_and_auto_create_cart(self, client):
        cart = await client.fetch_user_cart(123)
        assert cart is not None
        assert cart["items"] == []

    @pytest.mark.asyncio
    async def test_add_to_cart_then_fetch(self, client):
        ok = await client.add_product_to_cart(123, 1)
        assert ok
        cart = await client.fetch_user_cart(123)
        assert len(cart["items"]) == 1
        assert cart["items"][0]["product_name"] == "T-Shirt"

    @pytest.mark.asyncio
    async def test_add_to_cart_increments_existing(self, client):
        await client.add_product_to_cart(123, 1)
        await client.add_product_to_cart(123, 1)
        cart = await client.fetch_user_cart(123)
        assert cart["items"][0]["quantity"] == 2

    @pytest.mark.asyncio
    async def test_submit_order_clears_cart(self, client):
        await client.add_product_to_cart(123, 1)
        order = await client.submit_order(123, "addr")
        assert order is not None
        assert order["total_amount"] == "25.00"

        cart = await client.fetch_user_cart(123)
        assert cart["items"] == []

    @pytest.mark.asyncio
    async def test_submit_order_empty_cart_returns_none(self, client):
        order = await client.submit_order(123, "addr")
        assert order is None

    @pytest.mark.asyncio
    async def test_sync_user(self, client):
        await client.sync_user({"telegram_id": 999, "first_name": "Alice"})
        assert 999 in client.users

    @pytest.mark.asyncio
    async def test_fetch_product_detail(self, client):
        detail = await client.fetch_product_detail(1)
        assert detail is not None
        assert detail["name"] == "T-Shirt"

    @pytest.mark.asyncio
    async def test_fetch_product_detail_missing(self, client):
        detail = await client.fetch_product_detail(999)
        assert detail is None

    @pytest.mark.asyncio
    async def test_update_item_quantity_removes_at_zero(self, client):
        await client.add_product_to_cart(123, 1)
        cart = await client.fetch_user_cart(123)
        item_id = cart["items"][0]["id"]
        ok = await client.update_item_quantity(item_id, 0)
        assert ok
        cart = await client.fetch_user_cart(123)
        assert cart["items"] == []

    @pytest.mark.asyncio
    async def test_update_item_quantity_nonexistent_returns_false(self, client):
        ok = await client.update_item_quantity(99999, 2)
        assert ok is False


# ---------------------------------------------------------------------------
# HttpApiClient – uses mocked httpx so no real network
# ---------------------------------------------------------------------------


@pytest.fixture
def http_client() -> HttpApiClient:
    return HttpApiClient(base_url="http://fake.local/api/")


class TestHttpApiClient:
    """Verify the HTTP client calls the right endpoints."""

    def _mock_response(self, mocker, json_data=None, status=200):
        resp = mocker.Mock()
        resp.status_code = status
        resp.json.return_value = json_data
        return resp

    def _mock_404(self, mocker):
        resp = mocker.Mock()
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404", request=mocker.Mock(), response=mocker.Mock()
        )
        return resp

    # ---- fetch_products ---------------------------------------------------

    @pytest.mark.asyncio
    async def test_fetch_products_success(self, http_client, mocker):
        mock_client = mocker.patch("api_client.httpx.AsyncClient")
        mock_instance = mock_client.return_value.__aenter__.return_value
        mock_instance.get.return_value = self._mock_response(
            mocker, [{"id": 1, "name": "Platform T-Shirt"}]
        )
        result = await http_client.fetch_products()
        assert len(result) == 1
        assert result[0]["name"] == "Platform T-Shirt"

    @pytest.mark.asyncio
    async def test_fetch_products_handles_exception(self, http_client, mocker):
        mock_client = mocker.patch("api_client.httpx.AsyncClient")
        mock_instance = mock_client.return_value.__aenter__.return_value
        mock_instance.get.side_effect = httpx.HTTPError("Gateway timeout")
        result = await http_client.fetch_products()
        assert result == []

    @pytest.mark.asyncio
    async def test_fetch_products_non_list_returns_empty(self, http_client, mocker):
        mock_client = mocker.patch("api_client.httpx.AsyncClient")
        mock_instance = mock_client.return_value.__aenter__.return_value
        mock_instance.get.return_value = self._mock_response(mocker, {"id": 1})
        result = await http_client.fetch_products()
        assert result == []

    # ---- fetch_user_cart --------------------------------------------------

    @pytest.mark.asyncio
    async def test_fetch_user_cart_auto_creates_on_404(self, http_client, mocker):
        mock_client = mocker.patch("api_client.httpx.AsyncClient")
        mock_instance = mock_client.return_value.__aenter__.return_value
        mock_instance.get.side_effect = [
            self._mock_404(mocker),  # first GET fails → _get returns None
            self._mock_response(mocker, {"id": 1, "items": []}),  # second GET
        ]
        # POST must return a response with json() returning truthy data
        mock_instance.post.return_value = self._mock_response(
            mocker, {"id": 1}, status=201
        )
        result = await http_client.fetch_user_cart(999)
        assert mock_instance.post.call_count == 1
        assert result["id"] == 1

    @pytest.mark.asyncio
    async def test_fetch_user_cart_auto_create_fails_returns_none(
        self, http_client, mocker
    ):
        mock_client = mocker.patch("api_client.httpx.AsyncClient")
        mock_instance = mock_client.return_value.__aenter__.return_value
        mock_instance.get.return_value = self._mock_404(mocker)  # first GET fails
        # POST raises HTTPError → caught by _post → returns None
        mock_instance.post.side_effect = httpx.HTTPError("create failed")
        result = await http_client.fetch_user_cart(999)
        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_user_cart_non_dict_returns_none(self, http_client, mocker):
        mock_client = mocker.patch("api_client.httpx.AsyncClient")
        mock_instance = mock_client.return_value.__aenter__.return_value
        mock_instance.get.return_value = self._mock_response(mocker, [1, 2, 3])
        result = await http_client.fetch_user_cart(999)
        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_user_cart_post_fails_returns_none(self, http_client, mocker):
        mock_client = mocker.patch("api_client.httpx.AsyncClient")
        mock_instance = mock_client.return_value.__aenter__.return_value
        # First GET 404, POST raises error
        mock_instance.get.return_value = self._mock_404(mocker)
        mock_instance.post.side_effect = httpx.HTTPError("post failed")
        result = await http_client.fetch_user_cart(999)
        assert result is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "side_effect",
        [
            httpx.ConnectTimeout("timeout"),
            httpx.HTTPStatusError("500", request=None, response=None),
        ],
    )
    async def test_fetch_user_cart_handles_network_errors(
        self, http_client, mocker, side_effect
    ):
        mock_client = mocker.patch("api_client.httpx.AsyncClient")
        mock_instance = mock_client.return_value.__aenter__.return_value
        mock_instance.get.side_effect = side_effect
        result = await http_client.fetch_user_cart(999)
        assert result is None

    # ---- sync_user ---------------------------------------------------------

    @pytest.mark.asyncio
    async def test_sync_user_creates_new_profile(self, http_client, mocker):
        mock_client = mocker.patch("api_client.httpx.AsyncClient")
        mock_instance = mock_client.return_value.__aenter__.return_value
        mock_instance.get.return_value = self._mock_404(mocker)
        mock_instance.post.return_value = self._mock_response(mocker, status=201)
        await http_client.sync_user({"telegram_id": 123, "first_name": "Test"})
        mock_instance.get.assert_called_once()
        mock_instance.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_sync_user_updates_existing_profile(self, http_client, mocker):
        mock_client = mocker.patch("api_client.httpx.AsyncClient")
        mock_instance = mock_client.return_value.__aenter__.return_value
        mock_instance.get.return_value = self._mock_response(mocker, {"id": 123})
        mock_instance.patch.return_value = self._mock_response(mocker, status=200)
        await http_client.sync_user({"telegram_id": 123, "first_name": "Test"})
        mock_instance.patch.assert_called_once()
        mock_instance.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_sync_user_post_fails_silently(self, http_client, mocker):
        mock_client = mocker.patch("api_client.httpx.AsyncClient")
        mock_instance = mock_client.return_value.__aenter__.return_value
        mock_instance.get.return_value = self._mock_404(mocker)
        mock_instance.post.side_effect = httpx.HTTPError("fail")
        await http_client.sync_user({"telegram_id": 123, "first_name": "Test"})

    # ---- fetch_product_detail ---------------------------------------------

    @pytest.mark.asyncio
    async def test_fetch_product_detail_success(self, http_client, mocker):
        mock_client = mocker.patch("api_client.httpx.AsyncClient")
        mock_instance = mock_client.return_value.__aenter__.return_value
        mock_instance.get.return_value = self._mock_response(
            mocker, {"id": 1, "name": "Widget"}
        )
        result = await http_client.fetch_product_detail(1)
        assert result["name"] == "Widget"

    @pytest.mark.asyncio
    async def test_fetch_product_detail_non_dict_returns_none(
        self, http_client, mocker
    ):
        mock_client = mocker.patch("api_client.httpx.AsyncClient")
        mock_instance = mock_client.return_value.__aenter__.return_value
        mock_instance.get.return_value = self._mock_response(mocker, [1, 2])
        result = await http_client.fetch_product_detail(1)
        assert result is None

    # ---- add_product_to_cart ----------------------------------------------

    @pytest.mark.asyncio
    async def test_add_product_to_cart_existing_item(self, http_client, mocker):
        mock_client = mocker.patch("api_client.httpx.AsyncClient")
        mock_instance = mock_client.return_value.__aenter__.return_value
        mock_instance.get.return_value = self._mock_response(
            mocker,
            {
                "id": 1,
                "items": [{"id": 10, "product": 5, "quantity": 1}],
                "cart_total": "10.00",
            },
        )
        mock_instance.post.return_value = self._mock_response(
            mocker, {"id": 11}
        )
        ok = await http_client.add_product_to_cart(123, 5)
        assert ok is True
        # Now always POSTs — server-side handles dedup/increment
        mock_instance.post.assert_called_once()
        mock_instance.patch.assert_not_called()

    @pytest.mark.asyncio
    async def test_add_product_to_cart_new_item(self, http_client, mocker):
        mock_client = mocker.patch("api_client.httpx.AsyncClient")
        mock_instance = mock_client.return_value.__aenter__.return_value
        mock_instance.get.return_value = self._mock_response(
            mocker, {"id": 1, "items": [], "cart_total": "0.00"}
        )
        mock_instance.post.return_value = self._mock_response(
            mocker, {"id": 20}, status=201
        )
        ok = await http_client.add_product_to_cart(123, 5)
        assert ok is True
        mock_instance.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_product_to_cart_no_cart_returns_false(
        self, http_client, mocker
    ):
        mock_client = mocker.patch("api_client.httpx.AsyncClient")
        mock_instance = mock_client.return_value.__aenter__.return_value
        mock_instance.get.side_effect = httpx.HTTPError("no cart")
        ok = await http_client.add_product_to_cart(123, 5)
        assert ok is False

    # ---- update_item_quantity ---------------------------------------------

    @pytest.mark.asyncio
    async def test_update_item_quantity_zero_calls_delete(self, http_client, mocker):
        mock_client = mocker.patch("api_client.httpx.AsyncClient")
        mock_instance = mock_client.return_value.__aenter__.return_value
        mock_instance.delete.return_value = self._mock_response(mocker, status=204)
        ok = await http_client.update_item_quantity(10, 0)
        assert ok is True
        mock_instance.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_item_quantity_delete_fails(self, http_client, mocker):
        mock_client = mocker.patch("api_client.httpx.AsyncClient")
        mock_instance = mock_client.return_value.__aenter__.return_value
        mock_instance.delete.side_effect = httpx.HTTPError("delete failed")
        ok = await http_client.update_item_quantity(10, 0)
        assert ok is False

    @pytest.mark.asyncio
    async def test_update_item_quantity_positive_calls_patch(
        self, http_client, mocker
    ):
        mock_client = mocker.patch("api_client.httpx.AsyncClient")
        mock_instance = mock_client.return_value.__aenter__.return_value
        mock_instance.patch.return_value = self._mock_response(mocker, {"quantity": 3})
        ok = await http_client.update_item_quantity(10, 3)
        assert ok is True
        mock_instance.patch.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_item_quantity_patch_fails(self, http_client, mocker):
        mock_client = mocker.patch("api_client.httpx.AsyncClient")
        mock_instance = mock_client.return_value.__aenter__.return_value
        mock_instance.patch.side_effect = httpx.HTTPError("patch failed")
        ok = await http_client.update_item_quantity(10, 3)
        assert ok is False

    # ---- submit_order -----------------------------------------------------

    @pytest.mark.asyncio
    async def test_submit_order_success(self, http_client, mocker):
        mock_client = mocker.patch("api_client.httpx.AsyncClient")
        mock_instance = mock_client.return_value.__aenter__.return_value
        mock_instance.post.return_value = self._mock_response(
            mocker, {"id": 99, "status": "PENDING"}
        )
        result = await http_client.submit_order(123, "123 Main St")
        assert result["id"] == 99

    @pytest.mark.asyncio
    async def test_submit_order_non_dict_returns_none(self, http_client, mocker):
        mock_client = mocker.patch("api_client.httpx.AsyncClient")
        mock_instance = mock_client.return_value.__aenter__.return_value
        mock_instance.post.return_value = self._mock_response(mocker, [1, 2, 3])
        result = await http_client.submit_order(123, "addr")
        assert result is None

    # ---- private helpers ---------------------------------------------------

    @pytest.mark.asyncio
    async def test_patch_failure_returns_none(self, http_client, mocker):
        mock_client = mocker.patch("api_client.httpx.AsyncClient")
        mock_instance = mock_client.return_value.__aenter__.return_value
        mock_instance.patch.side_effect = httpx.HTTPError("patch fail")
        result = await http_client._patch("some/path/", json={})
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_failure_returns_false(self, http_client, mocker):
        mock_client = mocker.patch("api_client.httpx.AsyncClient")
        mock_instance = mock_client.return_value.__aenter__.return_value
        mock_instance.delete.side_effect = httpx.HTTPError("delete fail")
        result = await http_client._delete("some/path/")
        assert result is False

    @pytest.mark.asyncio
    async def test_post_failure_returns_none(self, http_client, mocker):
        mock_client = mocker.patch("api_client.httpx.AsyncClient")
        mock_instance = mock_client.return_value.__aenter__.return_value
        mock_instance.post.side_effect = httpx.HTTPError("post fail")
        result = await http_client._post("some/path/", json={})
        assert result is None