from datetime import datetime, time, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Pedido, Conversa, ConversaStatus, PedidoOrigem
from app.schemas import DashboardOverview
from app.routers.auth import get_current_user

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

@router.get("/overview", response_model=DashboardOverview)
def overview(db: Session = Depends(get_db), _=Depends(get_current_user)):
    # created_at e gravado em UTC (datetime.utcnow), entao usamos a mesma
    # base de tempo (UTC) para definir "hoje" e evitar descasamento de fuso.
    hoje = datetime.utcnow().date()
    # Filtro por RANGE de datetime, portavel entre PostgreSQL e SQLite
    # (evita strftime/func.date, que nao existem em todos os bancos).
    inicio = datetime.combine(hoje, time.min)
    fim = inicio + timedelta(days=1)
    pedidos_hoje = db.query(Pedido).filter(
        Pedido.created_at >= inicio,
        Pedido.created_at < fim,
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
