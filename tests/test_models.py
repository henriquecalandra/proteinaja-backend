import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models import Cliente, Conversa, Mensagem, Pedido, ClienteTipo, ConversaStatus, PedidoOrigem, PedidoStatus
import json

@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)

def test_criar_cliente(db):
    cliente = Cliente(nome="Açougue do João", whatsapp="5562999991234", tipo=ClienteTipo.acougue, cidade="Anápolis")
    db.add(cliente)
    db.commit()
    db.refresh(cliente)
    assert cliente.id is not None
    assert cliente.ativo is True

def test_criar_conversa_com_mensagens(db):
    cliente = Cliente(nome="Açougue do João", whatsapp="5562999991234", tipo=ClienteTipo.acougue)
    db.add(cliente)
    db.commit()
    conversa = Conversa(cliente_id=cliente.id)
    db.add(conversa)
    db.commit()
    msg = Mensagem(conversa_id=conversa.id, origem="cliente", texto="Quero 30kg de picanha")
    db.add(msg)
    db.commit()
    assert conversa.status == ConversaStatus.agente
    assert len(conversa.mensagens) == 1
    assert conversa.mensagens[0].texto == "Quero 30kg de picanha"

def test_criar_pedido(db):
    cliente = Cliente(nome="Açougue do João", whatsapp="5562999991234", tipo=ClienteTipo.acougue)
    db.add(cliente)
    db.commit()
    conversa = Conversa(cliente_id=cliente.id)
    db.add(conversa)
    db.commit()
    itens = [{"produto": "Picanha", "quantidade_kg": 30, "preco_kg": 89.0}]
    pedido = Pedido(
        conversa_id=conversa.id, cliente_id=cliente.id,
        itens_json=json.dumps(itens), valor_total=2670.0,
        origem=PedidoOrigem.ia, status=PedidoStatus.confirmado,
    )
    db.add(pedido)
    db.commit()
    db.refresh(pedido)
    assert pedido.id is not None
    assert pedido.valor_total == 2670.0
