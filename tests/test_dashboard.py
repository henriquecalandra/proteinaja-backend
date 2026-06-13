import pytest
import json
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import app
from app.database import Base, get_db
from app.models import Cliente, Conversa, Pedido, Usuario, ClienteTipo, PedidoOrigem, PedidoStatus
from app.services.auth import hash_senha, criar_token

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
def setup(request):
    app.dependency_overrides[get_db] = override_get_db
    db = SessionTest()
    usuario = Usuario(nome="Marcos", email="marcos@test.com", senha_hash=hash_senha("123"))
    db.add(usuario)
    cliente = Cliente(nome="Açougue", whatsapp="5562111", tipo=ClienteTipo.acougue)
    db.add(cliente)
    db.commit()
    conversa = Conversa(cliente_id=cliente.id)
    db.add(conversa)
    db.commit()
    pedido = Pedido(
        conversa_id=conversa.id, cliente_id=cliente.id,
        itens_json=json.dumps([{"produto": "Picanha", "quantidade_kg": 10}]),
        valor_total=890.0, origem=PedidoOrigem.ia, status=PedidoStatus.confirmado,
    )
    db.add(pedido)
    db.commit()
    db.close()
    yield
    Base.metadata.drop_all(engine_test)
    Base.metadata.create_all(engine_test)
    app.dependency_overrides.pop(get_db, None)

def auth_headers():
    token = criar_token("marcos@test.com")
    return {"Authorization": f"Bearer {token}"}

def test_overview_retorna_dados():
    r = client.get("/dashboard/overview", headers=auth_headers())
    assert r.status_code == 200
    data = r.json()
    assert data["pedidos_hoje"] == 1
    assert data["pedidos_agente_hoje"] == 1
    assert data["volume_hoje"] == 890.0
    assert data["pct_agente"] == 100.0

def test_listar_clientes():
    r = client.get("/clients/", headers=auth_headers())
    assert r.status_code == 200
    assert len(r.json()) == 1

def test_overview_sem_token():
    r = client.get("/dashboard/overview")
    assert r.status_code == 403
