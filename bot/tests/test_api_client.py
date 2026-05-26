import httpx
import pytest

from api_client import fetch_products, fetch_user_cart


@pytest.mark.asyncio
async def test_fetch_products_success(mocker):
    mock_client = mocker.patch("api_client.httpx.AsyncClient")
    mock_instance = mock_client.return_value.__aenter__.return_value

    mock_response = mocker.Mock()
    mock_response.json.return_value = [{"id": 1, "name": "Platform T-Shirt"}]
    mock_instance.get.return_value = mock_response

    result = await fetch_products()

    assert len(result) == 1
    assert result[0]["name"] == "Platform T-Shirt"


@pytest.mark.asyncio
async def test_fetch_products_handles_exception(mocker):
    mock_client = mocker.patch("api_client.httpx.AsyncClient")
    mock_instance = mock_client.return_value.__aenter__.return_value

    mock_instance.get.side_effect = httpx.HTTPError("Gateway timeout")

    result = await fetch_products()

    assert result == []


@pytest.mark.asyncio
async def test_fetch_user_cart_auto_creates_on_404(mocker):
    mock_client = mocker.patch("api_client.httpx.AsyncClient")
    mock_instance = mock_client.return_value.__aenter__.return_value

    mock_404 = mocker.Mock()
    mock_404.status_code = 404

    mock_201 = mocker.Mock()
    mock_201.status_code = 201

    mock_200 = mocker.Mock()
    mock_200.status_code = 200
    mock_200.json.return_value = {"id": 1, "items": []}

    mock_instance.get.side_effect = [mock_404, mock_200]
    mock_instance.post.return_value = mock_201

    result = await fetch_user_cart(999)

    assert mock_instance.post.call_count == 1
    assert mock_instance.get.call_count == 2
    assert result["id"] == 1


@pytest.mark.asyncio
async def test_sync_user_creates_new_profile(mocker):
    mock_client = mocker.patch("api_client.httpx.AsyncClient")
    mock_instance = mock_client.return_value.__aenter__.return_value

    # Simulate a 404 (user doesn't exist), then a 201 Created
    mock_404 = mocker.Mock()
    mock_404.status_code = 404
    mock_201 = mocker.Mock()
    mock_201.status_code = 201

    mock_instance.get.return_value = mock_404
    mock_instance.post.return_value = mock_201

    from api_client import sync_user

    await sync_user({"telegram_id": 123, "first_name": "Test"})

    mock_instance.get.assert_called_once()
    mock_instance.post.assert_called_once()


@pytest.mark.asyncio
async def test_submit_order_success(mocker):
    mock_client = mocker.patch("api_client.httpx.AsyncClient")
    mock_instance = mock_client.return_value.__aenter__.return_value

    mock_response = mocker.Mock()
    mock_response.json.return_value = {"id": 99, "status": "PENDING"}
    mock_instance.post.return_value = mock_response

    from api_client import submit_order

    result = await submit_order(123, "123 Main St")

    assert result["id"] == 99
    assert result["status"] == "PENDING"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "side_effect",
    [
        httpx.ConnectTimeout("timeout"),
        httpx.HTTPStatusError("500", request=None, response=None),
    ],
)
async def test_fetch_user_cart_handles_network_errors(mocker, side_effect):
    mock_client = mocker.patch("api_client.httpx.AsyncClient")
    mock_instance = mock_client.return_value.__aenter__.return_value

    # Force the network call to explode
    mock_instance.get.side_effect = side_effect

    from api_client import fetch_user_cart

    result = await fetch_user_cart(999)

    # Your current code returns None on error
    assert result is None


@pytest.mark.asyncio
async def test_sync_user_updates_existing_profile(mocker):
    mock_client = mocker.patch("api_client.httpx.AsyncClient")
    mock_instance = mock_client.return_value.__aenter__.return_value

    # Simulate 200 OK (user already exists)
    mock_200 = mocker.Mock()
    mock_200.status_code = 200

    mock_instance.get.return_value = mock_200
    mock_instance.patch.return_value = mocker.Mock(status_code=200)

    from api_client import sync_user

    await sync_user({"telegram_id": 123, "first_name": "Test"})

    # Verify PATCH was called instead of POST
    mock_instance.patch.assert_called_once()
    mock_instance.post.assert_not_called()
