from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Usuario
from app.schemas import LoginRequest, TokenResponse, RegisterRequest, UsuarioMe
from app.services.auth import verificar_senha, criar_token, verificar_token, hash_senha

router = APIRouter(prefix="/auth", tags=["auth"])
security = HTTPBearer()

@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.email == body.email).first()
    if not usuario or not verificar_senha(body.senha, usuario.senha_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas")
    return TokenResponse(access_token=criar_token(usuario.email))

@router.post("/register", response_model=TokenResponse)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(Usuario).filter(Usuario.email == body.email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="E-mail ja cadastrado")
    usuario = Usuario(nome=body.nome, email=body.email, senha_hash=hash_senha(body.senha))
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return TokenResponse(access_token=criar_token(usuario.email))

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    email = verificar_token(credentials.credentials)
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")
    usuario = db.query(Usuario).filter(Usuario.email == email).first()
    if not usuario:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário não encontrado")
    return usuario

def require_admin(usuario: Usuario = Depends(get_current_user)) -> Usuario:
    if usuario.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso restrito a administradores")
    return usuario

@router.get("/me", response_model=UsuarioMe)
def me(usuario: Usuario = Depends(get_current_user)):
    return UsuarioMe.model_validate(usuario)
