from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Empresa, Pedido, Cliente
from app.schemas import AdminOverview, EmpresaSchema
from app.routers.auth import require_admin

router = APIRouter(prefix="/admin", tags=["admin"])

@router.get("/overview", response_model=AdminOverview)
def overview(db: Session = Depends(get_db), _=Depends(require_admin)):
    total_empresas = db.query(func.count(Empresa.id)).scalar() or 0
    empresas_ativas = db.query(func.count(Empresa.id)).filter(Empresa.ativo.is_(True)).scalar() or 0
    total_pedidos = db.query(func.count(Pedido.id)).scalar() or 0
    gmv = db.query(func.coalesce(func.sum(Pedido.valor_total), 0.0)).scalar() or 0.0
    total_clientes = db.query(func.count(Cliente.id)).scalar() or 0
    return AdminOverview(
        total_empresas=total_empresas,
        empresas_ativas=empresas_ativas,
        total_pedidos_plataforma=total_pedidos,
        gmv_plataforma=float(gmv),
        total_clientes=total_clientes,
    )

@router.get("/companies", response_model=list[EmpresaSchema])
def companies(db: Session = Depends(get_db), _=Depends(require_admin)):
    empresas = db.query(Empresa).order_by(Empresa.nome).all()
    return [EmpresaSchema.model_validate(e) for e in empresas]
