from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Pedido
from app.schemas import PedidoSchema
from app.routers.auth import get_current_user

router = APIRouter(prefix="/orders", tags=["orders"])

@router.get("/", response_model=list[PedidoSchema])
def listar_pedidos(limit: int = 50, db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.query(Pedido).order_by(Pedido.created_at.desc()).limit(limit).all()
