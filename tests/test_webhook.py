import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import patch, AsyncMock
from app.main import app
from app.database import Base, get_db
from app.models import Cliente, Conversa, Mensagem

engine_test = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
SessionTest = sessionmaker(bind=engine_test)
Base.metadata.create_all(bind=engine_test)

def override_get_db():
    db = SessionTest()
    try:
        yield db
    finally:
        db.close()

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db_override():
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)
    # Clean up all records between tests
    db = SessionTest()
    db.query(Mensagem).delete()
    db.query(Conversa).delete()
    db.query(Cliente).delete()
    db.commit()
    db.close()

PAYLOAD_VALIDO = {
    "event": "messages.upsert",
    "data": {
        "key": {"fromMe": False, "remoteJid": "5562999991234@s.whatsapp.net"},
        "pushName": "João do Açougue",
        "message": {"conversation": "Quero 30kg de picanha"},
    }
}

def test_webhook_ignora_mensagem_propria():
    payload = {
        "event": "messages.upsert",
        "data": {
            "key": {"fromMe": True, "remoteJid": "5562999991234@s.whatsapp.net"},
            "pushName": "Test",
            "message": {"conversation": "msg"},
        }
    }
    r = client.post("/webhook/whatsapp", json=payload)
    assert r.status_code == 200
    db = SessionTest()
    assert db.query(Mensagem).count() == 0
    db.close()

def test_webhook_ignora_evento_desconhecido():
    r = client.post("/webhook/whatsapp", json={"event": "connection.update", "data": {}})
    assert r.status_code == 200

def test_webhook_cria_cliente_e_responde():
    mock_resposta = "Temos picanha a R$ 89/kg. Quantos kg você precisa?"
    with patch("app.routers.webhook.gerar_resposta", return_value=mock_resposta), \
         patch("app.routers.webhook.enviar_mensagem", new_callable=AsyncMock):
        r = client.post("/webhook/whatsapp", json=PAYLOAD_VALIDO)
        assert r.status_code == 200

    db = SessionTest()
    cliente = db.query(Cliente).filter(Cliente.whatsapp == "5562999991234").first()
    assert cliente is not None
    assert cliente.nome == "João do Açougue"
    conversa = db.query(Conversa).filter(Conversa.cliente_id == cliente.id).first()
    assert conversa is not None
    mensagens = db.query(Mensagem).filter(Mensagem.conversa_id == conversa.id).all()
    assert len(mensagens) == 2
    db.close()
