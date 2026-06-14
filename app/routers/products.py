from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Produto
from app.schemas import ProdutoSchema, ProdutoCreate, ProdutoUpdate
from app.routers.auth import get_current_user

router = APIRouter(prefix="/products", tags=["products"])


@router.get("/", response_model=list[ProdutoSchema])
def listar_produtos(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.query(Produto).order_by(Produto.nome).all()


@router.post("/", response_model=ProdutoSchema, status_code=201)
def criar_produto(body: ProdutoCreate, db: Session = Depends(get_db), _=Depends(get_current_user)):
    if db.query(Produto).filter(Produto.nome == body.nome).first():
        raise HTTPException(status_code=409, detail="Produto ja cadastrado")
    produto = Produto(
        nome=body.nome,
        preco_kg=body.preco_kg,
        categoria=body.categoria,
        ativo=body.ativo,
    )
    db.add(produto)
    db.commit()
    db.refresh(produto)
    return produto


@router.patch("/{produto_id}", response_model=ProdutoSchema)
def atualizar_produto(produto_id: int, body: ProdutoUpdate,
                      db: Session = Depends(get_db), _=Depends(get_current_user)):
    produto = db.query(Produto).filter(Produto.id == produto_id).first()
    if not produto:
        raise HTTPException(status_code=404, detail="Produto nao encontrado")
    dados = body.model_dump(exclude_unset=True)
    for campo, valor in dados.items():
        setattr(produto, campo, valor)
    db.commit()
    db.refresh(produto)
    return produto
