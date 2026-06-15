from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Vendedor, Usuario
from app.schemas import VendedorSchema, VendedorCreate, VendedorUpdate
from app.routers.auth import get_usuario_atual

router = APIRouter(prefix="/sellers", tags=["sellers"])


def _is_admin(usuario: Usuario) -> bool:
    return usuario.role == "admin"


@router.get("/", response_model=list[VendedorSchema])
def listar_vendedores(db: Session = Depends(get_db), usuario: Usuario = Depends(get_usuario_atual)):
    query = db.query(Vendedor)
    if not _is_admin(usuario):
        query = query.filter(Vendedor.empresa_id == usuario.empresa_id)
    return query.order_by(Vendedor.nome).all()


@router.post("/", response_model=VendedorSchema, status_code=201)
def criar_vendedor(body: VendedorCreate, db: Session = Depends(get_db), usuario: Usuario = Depends(get_usuario_atual)):
    vendedor = Vendedor(
        nome=body.nome,
        email=body.email,
        telefone=body.telefone,
        ativo=body.ativo,
        meta_mensal=body.meta_mensal,
        empresa_id=usuario.empresa_id,
    )
    db.add(vendedor)
    db.commit()
    db.refresh(vendedor)
    return vendedor


@router.patch("/{vendedor_id}", response_model=VendedorSchema)
def atualizar_vendedor(vendedor_id: int, body: VendedorUpdate,
                       db: Session = Depends(get_db), usuario: Usuario = Depends(get_usuario_atual)):
    query = db.query(Vendedor).filter(Vendedor.id == vendedor_id)
    if not _is_admin(usuario):
        query = query.filter(Vendedor.empresa_id == usuario.empresa_id)
    vendedor = query.first()
    if not vendedor:
        raise HTTPException(status_code=404, detail="Vendedor nao encontrado")
    dados = body.model_dump(exclude_unset=True)
    for campo, valor in dados.items():
        setattr(vendedor, campo, valor)
    db.commit()
    db.refresh(vendedor)
    return vendedor
