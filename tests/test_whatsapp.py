import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.whatsapp import enviar_mensagem

@pytest.mark.asyncio
async def test_enviar_mensagem_sucesso():
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)
    with patch("httpx.AsyncClient", return_value=mock_client):
        resultado = await enviar_mensagem("5562999991234", "Olá! Pedido confirmado.")
        assert resultado is True

@pytest.mark.asyncio
async def test_enviar_mensagem_falha():
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)
    with patch("httpx.AsyncClient", return_value=mock_client):
        resultado = await enviar_mensagem("5562999991234", "Olá!")
        assert resultado is False
