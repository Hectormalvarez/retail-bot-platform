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
