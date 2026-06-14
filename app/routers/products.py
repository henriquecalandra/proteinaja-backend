from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Produto, Usuario
from app.schemas import ProdutoSchema, ProdutoCreate, ProdutoUpdate
from app.routers.auth import get_usuario_atual

router = APIRouter(prefix="/products", tags=["products"])


def _is_admin(usuario: Usuario) -> bool:
    return usuario.role == "admin"


@router.get("/", response_model=list[ProdutoSchema])
def listar_produtos(db: Session = Depends(get_db), usuario: Usuario = Depends(get_usuario_atual)):
    query = db.query(Produto)
    if not _is_admin(usuario):
        query = query.filter(Produto.empresa_id == usuario.empresa_id)
    return query.order_by(Produto.nome).all()


@router.post("/", response_model=ProdutoSchema, status_code=201)
def criar_produto(body: ProdutoCreate, db: Session = Depends(get_db), usuario: Usuario = Depends(get_usuario_atual)):
    # Produtos sao por empresa: a unicidade do nome e dentro da empresa do usuario.
    if db.query(Produto).filter(
        Produto.nome == body.nome,
        Produto.empresa_id == usuario.empresa_id,
    ).first():
        raise HTTPException(status_code=409, detail="Produto ja cadastrado")
    produto = Produto(
        nome=body.nome,
        preco_kg=body.preco_kg,
        categoria=body.categoria,
        sku=body.sku,
        unidade=body.unidade,
        estoque=body.estoque,
        estoque_minimo=body.estoque_minimo,
        preco_custo=body.preco_custo,
        descricao=body.descricao,
        ativo=body.ativo,
        empresa_id=usuario.empresa_id,
    )
    db.add(produto)
    db.commit()
    db.refresh(produto)
    return produto


@router.patch("/{produto_id}", response_model=ProdutoSchema)
def atualizar_produto(produto_id: int, body: ProdutoUpdate,
                      db: Session = Depends(get_db), usuario: Usuario = Depends(get_usuario_atual)):
    query = db.query(Produto).filter(Produto.id == produto_id)
    if not _is_admin(usuario):
        query = query.filter(Produto.empresa_id == usuario.empresa_id)
    produto = query.first()
    if not produto:
        raise HTTPException(status_code=404, detail="Produto nao encontrado")
    dados = body.model_dump(exclude_unset=True)
    for campo, valor in dados.items():
        setattr(produto, campo, valor)
    db.commit()
    db.refresh(produto)
    return produto
