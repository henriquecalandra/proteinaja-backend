from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Conversa, Mensagem, ConversaStatus
from app.schemas import ConversaSchema, MensagemSchema
from app.routers.auth import get_current_user

router = APIRouter(prefix="/conversations", tags=["conversations"])

@router.get("/", response_model=list[ConversaSchema])
def listar_conversas(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.query(Conversa).filter(Conversa.status != ConversaStatus.encerrada)\
             .order_by(Conversa.updated_at.desc()).limit(50).all()

@router.get("/{conversa_id}/messages", response_model=list[MensagemSchema])
def mensagens_da_conversa(conversa_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.query(Mensagem).filter(Mensagem.conversa_id == conversa_id)\
             .order_by(Mensagem.created_at).all()

@router.post("/{conversa_id}/assume")
def assumir_conversa(conversa_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    conversa = db.query(Conversa).filter(Conversa.id == conversa_id).first()
    if conversa:
        conversa.status = ConversaStatus.humano
        db.commit()
    return {"ok": True}
