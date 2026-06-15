from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Cliente, Pedido, Conversa, Usuario
from app.schemas import (
    ClienteSchema,
    ClienteCreate,
    ClienteUpdate,
    ClienteDetalhe,
    ClienteInativo,
    ClienteReposicao,
)
from app.routers.auth import get_usuario_atual

router = APIRouter(prefix="/clients", tags=["clients"])


def _is_admin(usuario: Usuario) -> bool:
    return usuario.role == "admin"


def _to_dt(valor) -> datetime | None:
    """Parsing defensivo de created_at (datetime ou str ISO) -> datetime."""
    if valor is None:
        return None
    if isinstance(valor, datetime):
        return valor
    try:
        return datetime.fromisoformat(str(valor))
    except (ValueError, TypeError):
        return None


@router.get("/", response_model=list[ClienteSchema])
def listar_clientes(db: Session = Depends(get_db), usuario: Usuario = Depends(get_usuario_atual)):
    query = db.query(Cliente)
    if not _is_admin(usuario):
        query = query.filter(Cliente.empresa_id == usuario.empresa_id)
    clientes = query.order_by(Cliente.nome).all()
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

@router.post("/", response_model=ClienteSchema, status_code=201)
def criar_cliente(body: ClienteCreate, db: Session = Depends(get_db), usuario: Usuario = Depends(get_usuario_atual)):
    if db.query(Cliente).filter(Cliente.whatsapp == body.whatsapp).first():
        raise HTTPException(status_code=409, detail="WhatsApp ja cadastrado")
    cliente = Cliente(
        nome=body.nome,
        whatsapp=body.whatsapp,
        tipo=body.tipo,
        cnpj=body.cnpj,
        cidade=body.cidade,
        atendido_por_ia=body.atendido_por_ia,
        email=body.email,
        telefone=body.telefone,
        razao_social=body.razao_social,
        inscricao_estadual=body.inscricao_estadual,
        endereco=body.endereco,
        bairro=body.bairro,
        uf=body.uf,
        cep=body.cep,
        contato_nome=body.contato_nome,
        condicao_pagamento=body.condicao_pagamento,
        limite_credito=body.limite_credito,
        observacoes=body.observacoes,
        vendedor_id=body.vendedor_id,
        empresa_id=usuario.empresa_id,
    )
    db.add(cliente)
    db.commit()
    db.refresh(cliente)
    return ClienteSchema.model_validate(cliente)

@router.patch("/{cliente_id}", response_model=ClienteSchema)
def atualizar_cliente(cliente_id: int, body: ClienteUpdate,
                      db: Session = Depends(get_db), usuario: Usuario = Depends(get_usuario_atual)):
    query = db.query(Cliente).filter(Cliente.id == cliente_id)
    if not _is_admin(usuario):
        query = query.filter(Cliente.empresa_id == usuario.empresa_id)
    cliente = query.first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente nao encontrado")
    dados = body.model_dump(exclude_unset=True)
    for campo, valor in dados.items():
        setattr(cliente, campo, valor)
    db.commit()
    db.refresh(cliente)
    total_pedidos = db.query(func.count(Pedido.id))\
        .filter(Pedido.cliente_id == cliente.id).scalar() or 0
    valor_total = db.query(func.coalesce(func.sum(Pedido.valor_total), 0.0))\
        .filter(Pedido.cliente_id == cliente.id).scalar() or 0.0
    schema = ClienteSchema.model_validate(cliente)
    schema.total_pedidos = total_pedidos
    schema.valor_total_comprado = float(valor_total)
    return schema

@router.get("/inativos", response_model=list[ClienteInativo])
def clientes_inativos(
    dias: int = Query(30, ge=0),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    """Clientes sem pedido ha mais de 'dias' dias (ou que nunca compraram).

    Isolado por empresa (admin ve tudo). Ordenado por dias_sem_comprar desc.
    """
    query = db.query(Cliente)
    if not _is_admin(usuario):
        query = query.filter(Cliente.empresa_id == usuario.empresa_id)
    clientes = query.all()

    agora = datetime.utcnow()
    limite = agora - timedelta(days=dias)
    resultado: list[ClienteInativo] = []

    for cliente in clientes:
        pedidos = db.query(Pedido).filter(Pedido.cliente_id == cliente.id).all()
        datas = [d for d in (_to_dt(p.created_at) for p in pedidos) if d is not None]
        total_pedidos = len(pedidos)

        if datas:
            ultimo = max(datas)
            dias_sem = (agora - ultimo).days
            # so e inativo se o ultimo pedido for anterior ao limite
            if ultimo > limite:
                continue
            ultimo_iso = ultimo.isoformat()
        else:
            # nunca comprou -> sempre inativo
            ultimo = None
            dias_sem = (agora - _to_dt(cliente.created_at)).days if _to_dt(cliente.created_at) else 0
            ultimo_iso = None

        resultado.append(ClienteInativo(
            id=cliente.id,
            nome=cliente.nome,
            whatsapp=cliente.whatsapp,
            cidade=cliente.cidade,
            dias_sem_comprar=max(dias_sem, 0),
            ultimo_pedido=ultimo_iso,
            total_pedidos=total_pedidos,
        ))

    resultado.sort(key=lambda c: c.dias_sem_comprar, reverse=True)
    return resultado


@router.get("/reposicao", response_model=list[ClienteReposicao])
def clientes_reposicao(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    """Sugestao de reposicao para clientes com >=2 pedidos.

    Isolado por empresa (admin ve tudo). intervalo_medio = media dos gaps entre
    pedidos consecutivos; proxima_sugerida = ultimo + intervalo_medio;
    devido = proxima_sugerida <= hoje. Ordenado: devido primeiro.
    """
    query = db.query(Cliente)
    if not _is_admin(usuario):
        query = query.filter(Cliente.empresa_id == usuario.empresa_id)
    clientes = query.all()

    agora = datetime.utcnow()
    resultado: list[ClienteReposicao] = []

    for cliente in clientes:
        pedidos = db.query(Pedido).filter(Pedido.cliente_id == cliente.id).all()
        datas = sorted(d for d in (_to_dt(p.created_at) for p in pedidos) if d is not None)
        if len(datas) < 2:
            continue

        gaps = [(datas[i] - datas[i - 1]).total_seconds() / 86400.0 for i in range(1, len(datas))]
        intervalo_medio = sum(gaps) / len(gaps)
        ultimo = datas[-1]
        proxima = ultimo + timedelta(days=intervalo_medio)
        devido = proxima <= agora

        resultado.append(ClienteReposicao(
            id=cliente.id,
            nome=cliente.nome,
            whatsapp=cliente.whatsapp,
            intervalo_medio_dias=round(intervalo_medio, 1),
            ultimo_pedido=ultimo.isoformat(),
            proxima_sugerida=proxima.isoformat(),
            devido=devido,
        ))

    resultado.sort(key=lambda c: c.devido, reverse=True)
    return resultado


@router.get("/{cliente_id}", response_model=ClienteDetalhe)
def detalhe_cliente(cliente_id: int, db: Session = Depends(get_db), usuario: Usuario = Depends(get_usuario_atual)):
    query = db.query(Cliente).filter(Cliente.id == cliente_id)
    if not _is_admin(usuario):
        query = query.filter(Cliente.empresa_id == usuario.empresa_id)
    cliente = query.first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente nao encontrado")
    total_pedidos = db.query(func.count(Pedido.id))\
        .filter(Pedido.cliente_id == cliente.id).scalar() or 0
    valor_total = db.query(func.coalesce(func.sum(Pedido.valor_total), 0.0))\
        .filter(Pedido.cliente_id == cliente.id).scalar() or 0.0
    cliente_schema = ClienteSchema.model_validate(cliente)
    cliente_schema.total_pedidos = total_pedidos
    cliente_schema.valor_total_comprado = float(valor_total)
    pedidos = db.query(Pedido).filter(Pedido.cliente_id == cliente_id)\
        .order_by(Pedido.created_at.desc()).all()
    conversas = db.query(Conversa).filter(Conversa.cliente_id == cliente_id)\
        .order_by(Conversa.updated_at.desc()).all()
    return ClienteDetalhe(cliente=cliente_schema, pedidos=pedidos, conversas=conversas)
