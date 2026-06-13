from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Cliente
from app.schemas import ClienteSchema
from app.routers.auth import get_current_user

router = APIRouter(prefix="/clients", tags=["clients"])

@router.get("/", response_model=list[ClienteSchema])
def listar_clientes(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.query(Cliente).order_by(Cliente.nome).all()
