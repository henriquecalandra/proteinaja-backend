from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Pedido, PedidoStatus
from app.schemas import PedidoSchema
from app.routers.auth import get_current_user

router = APIRouter(prefix="/orders", tags=["orders"])


class AtualizarStatusRequest(BaseModel):
    status: str


@router.get("/", response_model=list[PedidoSchema])
def listar_pedidos(limit: int = 50, db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.query(Pedido).order_by(Pedido.created_at.desc()).limit(limit).all()

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
