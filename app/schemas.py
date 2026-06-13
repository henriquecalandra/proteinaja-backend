from pydantic import BaseModel
from datetime import datetime
from app.models import ClienteTipo, ConversaStatus, PedidoStatus, PedidoOrigem

class LoginRequest(BaseModel):
    email: str
    senha: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class ClienteSchema(BaseModel):
    id: int
    nome: str
    whatsapp: str
    tipo: ClienteTipo
    cidade: str | None
    ativo: bool
    created_at: datetime
    model_config = {"from_attributes": True}

class MensagemSchema(BaseModel):
    id: int
    origem: str
    texto: str
    created_at: datetime
    model_config = {"from_attributes": True}

class ConversaSchema(BaseModel):
    id: int
    cliente_id: int
    status: ConversaStatus
    updated_at: datetime
    model_config = {"from_attributes": True}

class PedidoSchema(BaseModel):
    id: int
    cliente_id: int
    itens_json: str
    valor_total: float
    origem: PedidoOrigem
    status: PedidoStatus
    created_at: datetime
    model_config = {"from_attributes": True}

class DashboardOverview(BaseModel):
    pedidos_hoje: int
    pedidos_agente_hoje: int
    conversas_ativas: int
    volume_hoje: float
    pct_agente: float
