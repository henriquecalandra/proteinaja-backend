from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Cliente, Pedido
from app.schemas import ClienteSchema
from app.routers.auth import get_current_user

router = APIRouter(prefix="/clients", tags=["clients"])

@router.get("/", response_model=list[ClienteSchema])
def listar_clientes(db: Session = Depends(get_db), _=Depends(get_current_user)):
    clientes = db.query(Cliente).order_by(Cliente.nome).all()
    resultado = []
    for cliente in clientes:
        total_pedidos = db.query(func.count(Pedido.id))\
            .filter(Pedido.cliente_id == cliente.id).scalar() or 0
        valor_total = db.query(func.coalesce(func.sum(Pedido.valor_total), 0.0))\
            .filter(Pedido.cliente_id == cliente.id).scalar() or 0.0
        schema = ClienteSchema.model_validate(cliente)
        schema.total_pedidos = total_pedidos
        schema.valor_total_comprado = float(valor_total)
        resultado.append(schema)
    return resultado
