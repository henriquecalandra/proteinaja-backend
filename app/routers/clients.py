from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Cliente, Pedido, Conversa, Usuario
from app.schemas import ClienteSchema, ClienteCreate, ClienteUpdate, ClienteDetalhe
from app.routers.auth import get_usuario_atual

router = APIRouter(prefix="/clients", tags=["clients"])


def _is_admin(usuario: Usuario) -> bool:
    return usuario.role == "admin"


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
