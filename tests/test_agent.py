import pytest
from unittest.mock import patch, MagicMock
from app.services.agent import gerar_resposta, deve_escalar_para_humano, montar_historico
from app.models import Cliente, ClienteTipo

def make_cliente():
    c = Cliente()
    c.nome = "Açougue do João"
    c.tipo = ClienteTipo.acougue
    c.cidade = "Anápolis"
    return c

def test_montar_historico_vazio():
    assert montar_historico([]) == []

def test_montar_historico_com_mensagens():
    msgs = [
        MagicMock(origem="cliente", texto="Quero picanha"),
        MagicMock(origem="agente", texto="Temos picanha a R$89/kg"),
    ]
    resultado = montar_historico(msgs)
    assert len(resultado) == 2
    assert resultado[0]["role"] == "user"
    assert resultado[1]["role"] == "assistant"

def test_deve_escalar_para_humano_true():
    assert deve_escalar_para_humano("preciso verificar com o gerente esse desconto") is True

def test_deve_escalar_para_humano_false():
    assert deve_escalar_para_humano("Pedido confirmado! Entrega em 2 dias úteis.") is False

def test_gerar_resposta_chama_claude():
    mock_content = MagicMock()
    mock_content.text = "Temos picanha a R$ 89/kg. Quantos kg você precisa?"
    mock_response = MagicMock()
    mock_response.content = [mock_content]
    with patch("app.services.agent.client_anthropic.messages.create", return_value=mock_response):
        resposta = gerar_resposta("Tem picanha?", [], make_cliente())
        assert "picanha" in resposta.lower()
