from datetime import date
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models import Pedido, Conversa, ConversaStatus, PedidoOrigem
from app.schemas import DashboardOverview
from app.routers.auth import get_current_user

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

@router.get("/overview", response_model=DashboardOverview)
def overview(db: Session = Depends(get_db), _=Depends(get_current_user)):
    hoje = date.today()
    # Use strftime for SQLite compatibility; PostgreSQL also supports this via func.date
    pedidos_hoje = db.query(Pedido).filter(
        func.strftime('%Y-%m-%d', Pedido.created_at) == hoje.isoformat()
    ).all()
    pedidos_agente = [p for p in pedidos_hoje if p.origem == PedidoOrigem.ia]
    conversas_ativas = db.query(Conversa).filter(Conversa.status != ConversaStatus.encerrada).count()
    volume_hoje = sum(p.valor_total for p in pedidos_hoje)
    total = len(pedidos_hoje)
    return DashboardOverview(
        pedidos_hoje=total,
        pedidos_agente_hoje=len(pedidos_agente),
        conversas_ativas=conversas_ativas,
        volume_hoje=volume_hoje,
        pct_agente=round(len(pedidos_agente) / total * 100, 1) if total > 0 else 0.0,
    )
