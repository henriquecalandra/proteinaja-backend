import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import app
from app.database import Base, get_db
from app.models import Usuario
from app.services.auth import hash_senha

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

@pytest.fixture(autouse=True)
def setup_db_override():
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)

client = TestClient(app)

@pytest.fixture(autouse=True)
def seed_usuario(setup_db_override):
    db = SessionTest()
    db.add(Usuario(nome="Marcos", email="marcos@frigorifico.com", senha_hash=hash_senha("senha123")))
    db.commit()
    yield
    db.query(Usuario).delete()
    db.commit()
    db.close()

def test_login_sucesso():
    r = client.post("/auth/login", json={"email": "marcos@frigorifico.com", "senha": "senha123"})
    assert r.status_code == 200
    assert "access_token" in r.json()

def test_login_senha_errada():
    r = client.post("/auth/login", json={"email": "marcos@frigorifico.com", "senha": "errada"})
    assert r.status_code == 401

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
