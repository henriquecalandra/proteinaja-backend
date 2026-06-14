import hashlib
import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Pedido, PedidoStatus, PedidoOrigem, Cliente, Conversa, ConversaStatus
from app.schemas import PedidoSchema, PedidoCreate
from app.routers.auth import get_current_user

router = APIRouter(prefix="/orders", tags=["orders"])

METODOS_PAGAMENTO_VALIDOS = ("pix", "boleto")


class AtualizarStatusRequest(BaseModel):
    status: str


class PagamentoRequest(BaseModel):
    metodo: str


@router.get("/", response_model=list[PedidoSchema])
def listar_pedidos(limit: int = 50, db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.query(Pedido).order_by(Pedido.created_at.desc()).limit(limit).all()

@router.post("/", response_model=PedidoSchema, status_code=201)
def criar_pedido(body: PedidoCreate, db: Session = Depends(get_db), _=Depends(get_current_user)):
    cliente = db.query(Cliente).filter(Cliente.id == body.cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente nao encontrado")

    itens = [
        {"produto": item.produto, "qtd_kg": item.qtd_kg, "preco_kg": item.preco_kg}
        for item in body.itens
    ]
    valor_total = sum(item.qtd_kg * item.preco_kg for item in body.itens)

    # Pedido.conversa_id e NOT NULL: reusa a conversa mais recente do cliente
    # ou cria uma nova conversa para ele.
    conversa = (
        db.query(Conversa)
        .filter(Conversa.cliente_id == cliente.id)
        .order_by(Conversa.updated_at.desc())
        .first()
    )
    if not conversa:
        conversa = Conversa(cliente_id=cliente.id, status=ConversaStatus.humano)
        db.add(conversa)
        db.commit()
        db.refresh(conversa)

    pedido = Pedido(
        conversa_id=conversa.id,
        cliente_id=cliente.id,
        itens_json=json.dumps(itens, ensure_ascii=False),
        valor_total=valor_total,
        origem=PedidoOrigem.humano,
        status=body.status,
    )
    db.add(pedido)
    db.commit()
    db.refresh(pedido)
    return pedido

@router.patch("/{pedido_id}", response_model=PedidoSchema)
def atualizar_status(pedido_id: int, body: AtualizarStatusRequest,
                     db: Session = Depends(get_db), _=Depends(get_current_user)):
    pedido = db.query(Pedido).filter(Pedido.id == pedido_id).first()
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido nao encontrado")
    try:
        novo_status = PedidoStatus(body.status)
    except ValueError:
        raise HTTPException(status_code=422, detail="Status invalido")
    pedido.status = novo_status
    db.commit()
    db.refresh(pedido)
    return pedido


@router.post("/{pedido_id}/payment", response_model=PedidoSchema)
def gerar_pagamento(pedido_id: int, body: PagamentoRequest,
                    db: Session = Depends(get_db), _=Depends(get_current_user)):
    pedido = db.query(Pedido).filter(Pedido.id == pedido_id).first()
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido nao encontrado")

    metodo = (body.metodo or "").lower()
    if metodo not in METODOS_PAGAMENTO_VALIDOS:
        raise HTTPException(status_code=422, detail="Metodo de pagamento invalido")

    # Identificador FAKE DETERMINISTICO derivado de (pedido_id, metodo).
    digest = hashlib.sha256(f"{pedido_id}-{metodo}".encode("utf-8")).hexdigest()
    if metodo == "pix":
        # "Copia e cola" fake: prefixo + hash em maiusculas.
        link = "00020126FAKE" + digest[:40].upper()
    else:
        # Boleto: linha digitavel fake de digitos (47 posicoes).
        digitos = "".join(str(int(ch, 16) % 10) for ch in digest)[:47]
        link = digitos

    pedido.metodo_pagamento = metodo
    pedido.link_pagamento = link
    pedido.pago = False
    db.commit()
    db.refresh(pedido)
    return pedido


@router.post("/{pedido_id}/pay", response_model=PedidoSchema)
def marcar_pago(pedido_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    pedido = db.query(Pedido).filter(Pedido.id == pedido_id).first()
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido nao encontrado")
    pedido.pago = True
    db.commit()
    db.refresh(pedido)
    return pedido
