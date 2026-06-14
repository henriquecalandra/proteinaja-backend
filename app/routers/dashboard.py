import json
from datetime import datetime, time, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Pedido, Conversa, ConversaStatus, PedidoOrigem, PedidoStatus, Cliente, Usuario
from app.schemas import (
    DashboardOverview,
    DashboardAnalytics,
    FaturamentoDia,
    PedidosPorStatus,
    TopProduto,
    TopCliente,
)
from app.routers.auth import get_usuario_atual

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _is_admin(usuario: Usuario) -> bool:
    return usuario.role == "admin"


@router.get("/overview", response_model=DashboardOverview)
def overview(db: Session = Depends(get_db), usuario: Usuario = Depends(get_usuario_atual)):
    # created_at e gravado em UTC (datetime.utcnow), entao usamos a mesma
    # base de tempo (UTC) para definir "hoje" e evitar descasamento de fuso.
    hoje = datetime.utcnow().date()
    # Filtro por RANGE de datetime, portavel entre PostgreSQL e SQLite
    # (evita strftime/func.date, que nao existem em todos os bancos).
    inicio = datetime.combine(hoje, time.min)
    fim = inicio + timedelta(days=1)

    admin = _is_admin(usuario)
    empresa_id = usuario.empresa_id

    pedidos_q = db.query(Pedido).filter(
        Pedido.created_at >= inicio,
        Pedido.created_at < fim,
    )
    if not admin:
        pedidos_q = pedidos_q.filter(Pedido.empresa_id == empresa_id)
    pedidos_hoje = pedidos_q.all()

    pedidos_agente = [p for p in pedidos_hoje if p.origem == PedidoOrigem.ia]

    conversas_q = db.query(Conversa).filter(Conversa.status != ConversaStatus.encerrada)
    if not admin:
        conversas_q = conversas_q.filter(Conversa.empresa_id == empresa_id)
    conversas_ativas = conversas_q.count()

    volume_hoje = sum(p.valor_total for p in pedidos_hoje)
    total = len(pedidos_hoje)
    return DashboardOverview(
        pedidos_hoje=total,
        pedidos_agente_hoje=len(pedidos_agente),
        conversas_ativas=conversas_ativas,
        volume_hoje=volume_hoje,
        pct_agente=round(len(pedidos_agente) / total * 100, 1) if total > 0 else 0.0,
    )


@router.get("/analytics", response_model=DashboardAnalytics)
def analytics(db: Session = Depends(get_db), usuario: Usuario = Depends(get_usuario_atual)):
    admin = _is_admin(usuario)
    empresa_id = usuario.empresa_id

    pedidos_q = db.query(Pedido)
    if not admin:
        pedidos_q = pedidos_q.filter(Pedido.empresa_id == empresa_id)
    pedidos = pedidos_q.all()

    # --- faturamento_por_dia: ultimos 14 dias (UTC), incluindo dias com 0 ---
    hoje = datetime.utcnow().date()
    dias = [hoje - timedelta(days=i) for i in range(13, -1, -1)]
    fat_map: dict[str, dict] = {d.isoformat(): {"total": 0.0, "qtd": 0} for d in dias}
    for p in pedidos:
        chave = p.created_at.date().isoformat() if p.created_at else None
        if chave in fat_map:
            fat_map[chave]["total"] += p.valor_total or 0.0
            fat_map[chave]["qtd"] += 1
    faturamento_por_dia = [
        FaturamentoDia(dia=d.isoformat(), total=round(fat_map[d.isoformat()]["total"], 2),
                       qtd=fat_map[d.isoformat()]["qtd"])
        for d in dias
    ]

    # --- pedidos_por_status ---
    status_count = {"confirmado": 0, "negociando": 0, "aguardando": 0, "entregue": 0}
    for p in pedidos:
        st = p.status.value if isinstance(p.status, PedidoStatus) else str(p.status)
        if st in status_count:
            status_count[st] += 1
    pedidos_por_status = PedidosPorStatus(**status_count)

    # --- top_produtos: parse defensivo de itens_json ---
    prod_agg: dict[str, dict] = {}
    for p in pedidos:
        try:
            itens = json.loads(p.itens_json) if p.itens_json else []
        except Exception:
            itens = []
        if not isinstance(itens, list):
            continue
        for item in itens:
            try:
                nome = item.get("produto")
                qtd = float(item.get("qtd_kg") or 0)
                preco = float(item.get("preco_kg") or 0)
            except Exception:
                continue
            if not nome:
                continue
            agg = prod_agg.setdefault(nome, {"qtd_kg": 0.0, "receita": 0.0})
            agg["qtd_kg"] += qtd
            agg["receita"] += qtd * preco
    top_produtos = [
        TopProduto(produto=nome, qtd_kg=round(v["qtd_kg"], 2), receita=round(v["receita"], 2))
        for nome, v in sorted(prod_agg.items(), key=lambda kv: kv[1]["receita"], reverse=True)[:5]
    ]

    # --- top_clientes: soma de valor_total por cliente ---
    cli_agg: dict[int, float] = {}
    for p in pedidos:
        cli_agg[p.cliente_id] = cli_agg.get(p.cliente_id, 0.0) + (p.valor_total or 0.0)
    top_ids = sorted(cli_agg.items(), key=lambda kv: kv[1], reverse=True)[:5]
    nomes = {
        c.id: c.nome
        for c in db.query(Cliente).filter(Cliente.id.in_([cid for cid, _ in top_ids])).all()
    } if top_ids else {}
    top_clientes = [
        TopCliente(nome=nomes.get(cid, f"Cliente {cid}"), total=round(total, 2))
        for cid, total in top_ids
    ]

    # --- ticket_medio / total_a_receber / total_pago ---
    n = len(pedidos)
    soma_total = sum(p.valor_total or 0.0 for p in pedidos)
    ticket_medio = round(soma_total / n, 2) if n else 0.0
    total_a_receber = round(sum(p.valor_total or 0.0 for p in pedidos if not p.pago), 2)
    total_pago = round(sum(p.valor_total or 0.0 for p in pedidos if p.pago), 2)

    return DashboardAnalytics(
        faturamento_por_dia=faturamento_por_dia,
        pedidos_por_status=pedidos_por_status,
        top_produtos=top_produtos,
        top_clientes=top_clientes,
        ticket_medio=ticket_medio,
        total_a_receber=total_a_receber,
        total_pago=total_pago,
    )
