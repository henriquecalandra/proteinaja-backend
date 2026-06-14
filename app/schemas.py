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
    cnpj: str | None
    whatsapp: str
    tipo: ClienteTipo
    cidade: str | None
    ativo: bool
    atendido_por_ia: bool
    created_at: datetime
    total_pedidos: int = 0
    valor_total_comprado: float = 0.0
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
    cliente_nome: str
    status: ConversaStatus
    updated_at: datetime
    model_config = {"from_attributes": True}

class PedidoSchema(BaseModel):
    id: int
    cliente_id: int
    cliente_nome: str
    itens_json: str
    valor_total: float
    origem: PedidoOrigem
    status: PedidoStatus
    metodo_pagamento: str | None = None
    pago: bool = False
    link_pagamento: str | None = None
    created_at: datetime
    model_config = {"from_attributes": True}

class DashboardOverview(BaseModel):
    pedidos_hoje: int
    pedidos_agente_hoje: int
    conversas_ativas: int
    volume_hoje: float
    pct_agente: float

class ClienteDetalhe(BaseModel):
    cliente: ClienteSchema
    pedidos: list[PedidoSchema]
    conversas: list[ConversaSchema]

# ---- Request schemas (Pydantic v2) ----

class RegisterRequest(BaseModel):
    nome: str
    email: str
    senha: str
    nome_empresa: str | None = None

class ClienteCreate(BaseModel):
    nome: str
    whatsapp: str
    tipo: ClienteTipo
    cnpj: str | None = None
    cidade: str | None = None
    atendido_por_ia: bool = True

class ClienteUpdate(BaseModel):
    nome: str | None = None
    cnpj: str | None = None
    cidade: str | None = None
    tipo: ClienteTipo | None = None
    ativo: bool | None = None
    atendido_por_ia: bool | None = None

class ItemPedidoIn(BaseModel):
    produto: str
    qtd_kg: float
    preco_kg: float

class PedidoCreate(BaseModel):
    cliente_id: int
    itens: list[ItemPedidoIn]
    status: PedidoStatus = PedidoStatus.aguardando

class ProdutoSchema(BaseModel):
    id: int
    nome: str
    categoria: str | None
    preco_kg: float
    ativo: bool
    created_at: datetime
    model_config = {"from_attributes": True}

class ProdutoCreate(BaseModel):
    nome: str
    preco_kg: float
    categoria: str | None = None
    ativo: bool = True

class ProdutoUpdate(BaseModel):
    nome: str | None = None
    preco_kg: float | None = None
    categoria: str | None = None
    ativo: bool | None = None

# ---- Multi-tenant: Empresa / Admin / Usuario ----

class EmpresaSchema(BaseModel):
    id: int
    nome: str
    cnpj: str | None = None
    cidade: str | None = None
    plano: str
    ativo: bool
    whatsapp_numero: str | None = None
    evolution_url: str | None = None
    evolution_instance: str | None = None
    whatsapp_conectado: bool
    email_contato: str | None = None
    telefone: str | None = None
    endereco: str | None = None
    responsavel: str | None = None
    segmento: str | None = None
    created_at: datetime
    model_config = {"from_attributes": True}

class EmpresaUpdate(BaseModel):
    nome: str | None = None
    cnpj: str | None = None
    cidade: str | None = None
    whatsapp_numero: str | None = None
    evolution_url: str | None = None
    evolution_instance: str | None = None
    email_contato: str | None = None
    telefone: str | None = None
    endereco: str | None = None
    responsavel: str | None = None
    segmento: str | None = None

class AdminOverview(BaseModel):
    total_empresas: int
    empresas_ativas: int
    total_pedidos_plataforma: int
    gmv_plataforma: float
    total_clientes: int

class UsuarioMe(BaseModel):
    id: int
    nome: str
    email: str
    role: str
    empresa_id: int | None = None
    model_config = {"from_attributes": True}

# ---- Dashboard analitico ----

class FaturamentoDia(BaseModel):
    dia: str
    total: float
    qtd: int

class PedidosPorStatus(BaseModel):
    confirmado: int
    negociando: int
    aguardando: int
    entregue: int

class TopProduto(BaseModel):
    produto: str
    qtd_kg: float
    receita: float

class TopCliente(BaseModel):
    nome: str
    total: float

class DashboardAnalytics(BaseModel):
    faturamento_por_dia: list[FaturamentoDia]
    pedidos_por_status: PedidosPorStatus
    top_produtos: list[TopProduto]
    top_clientes: list[TopCliente]
    ticket_medio: float
    total_a_receber: float
    total_pago: float
