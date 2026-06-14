from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Cliente, Pedido
from app.schemas import ClienteSchema, ClienteCreate, ClienteUpdate
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

@router.post("/", response_model=ClienteSchema, status_code=201)
def criar_cliente(body: ClienteCreate, db: Session = Depends(get_db), _=Depends(get_current_user)):
    if db.query(Cliente).filter(Cliente.whatsapp == body.whatsapp).first():
        raise HTTPException(status_code=409, detail="WhatsApp ja cadastrado")
    cliente = Cliente(
        nome=body.nome,
        whatsapp=body.whatsapp,
        tipo=body.tipo,
        cnpj=body.cnpj,
        cidade=body.cidade,
        atendido_por_ia=body.atendido_por_ia,
    )
    db.add(cliente)
    db.commit()
    db.refresh(cliente)
    return ClienteSchema.model_validate(cliente)

@router.patch("/{cliente_id}", response_model=ClienteSchema)
def atualizar_cliente(cliente_id: int, body: ClienteUpdate,
                      db: Session = Depends(get_db), _=Depends(get_current_user)):
    cliente = db.query(Cliente).filter(Cliente.id == cliente_id).first()
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
