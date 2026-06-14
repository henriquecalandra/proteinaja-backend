from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Empresa, Usuario
from app.schemas import EmpresaSchema, EmpresaUpdate
from app.routers.auth import get_current_user

router = APIRouter(prefix="/company", tags=["company"])


def _empresa_do_usuario(usuario: Usuario, db: Session) -> Empresa:
    if not usuario.empresa_id:
        raise HTTPException(status_code=404, detail="Usuario sem empresa associada")
    empresa = db.query(Empresa).filter(Empresa.id == usuario.empresa_id).first()
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa nao encontrada")
    return empresa


@router.get("", response_model=EmpresaSchema)
def get_company(db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    empresa = _empresa_do_usuario(usuario, db)
    return EmpresaSchema.model_validate(empresa)


@router.patch("", response_model=EmpresaSchema)
def update_company(body: EmpresaUpdate, db: Session = Depends(get_db),
                   usuario: Usuario = Depends(get_current_user)):
    empresa = _empresa_do_usuario(usuario, db)
    dados = body.model_dump(exclude_unset=True)
    for campo, valor in dados.items():
        setattr(empresa, campo, valor)
    db.commit()
    db.refresh(empresa)
    return EmpresaSchema.model_validate(empresa)


@router.post("/whatsapp/connect", response_model=EmpresaSchema)
def connect_whatsapp(db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    empresa = _empresa_do_usuario(usuario, db)
    if not empresa.whatsapp_numero:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Numero de WhatsApp e obrigatorio para conectar",
        )
    empresa.whatsapp_conectado = True
    db.commit()
    db.refresh(empresa)
    return EmpresaSchema.model_validate(empresa)


@router.post("/whatsapp/disconnect", response_model=EmpresaSchema)
def disconnect_whatsapp(db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    empresa = _empresa_do_usuario(usuario, db)
    empresa.whatsapp_conectado = False
    db.commit()
    db.refresh(empresa)
    return EmpresaSchema.model_validate(empresa)
