from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, Text, Enum, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
import enum

class ClienteTipo(str, enum.Enum):
    acougue = "acougue"
    restaurante = "restaurante"
    mercadinho = "mercadinho"
    food_service = "food_service"

class ConversaStatus(str, enum.Enum):
    agente = "agente"
    humano = "humano"
    encerrada = "encerrada"

class PedidoStatus(str, enum.Enum):
    confirmado = "confirmado"
    negociando = "negociando"
    aguardando = "aguardando"
    entregue = "entregue"

class PedidoOrigem(str, enum.Enum):
    ia = "ia"
    humano = "humano"

class Cliente(Base):
    __tablename__ = "clientes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(200))
    cnpj: Mapped[str | None] = mapped_column(String(18), unique=True)
    whatsapp: Mapped[str] = mapped_column(String(20), unique=True)
    tipo: Mapped[ClienteTipo] = mapped_column(Enum(ClienteTipo))
    cidade: Mapped[str | None] = mapped_column(String(100))
    empresa_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ativo: Mapped[bool] = mapped_column(default=True)
    atendido_por_ia: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # --- Cadastro completo do cliente (todas nullable) ---
    email: Mapped[str | None] = mapped_column(String(200), default=None)
    telefone: Mapped[str | None] = mapped_column(String(40), default=None)
    razao_social: Mapped[str | None] = mapped_column(String(200), default=None)
    inscricao_estadual: Mapped[str | None] = mapped_column(String(40), default=None)
    endereco: Mapped[str | None] = mapped_column(Text, default=None)
    bairro: Mapped[str | None] = mapped_column(String(100), default=None)
    uf: Mapped[str | None] = mapped_column(String(2), default=None)
    cep: Mapped[str | None] = mapped_column(String(15), default=None)
    contato_nome: Mapped[str | None] = mapped_column(String(200), default=None)
    condicao_pagamento: Mapped[str | None] = mapped_column(String(40), default=None)
    limite_credito: Mapped[float | None] = mapped_column(Float, default=None)
    observacoes: Mapped[str | None] = mapped_column(Text, default=None)
    vendedor_id: Mapped[int | None] = mapped_column(Integer, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    conversas: Mapped[list["Conversa"]] = relationship(back_populates="cliente")

class Conversa(Base):
    __tablename__ = "conversas"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id"))
    empresa_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[ConversaStatus] = mapped_column(Enum(ConversaStatus), default=ConversaStatus.agente)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    cliente: Mapped["Cliente"] = relationship(back_populates="conversas")
    mensagens: Mapped[list["Mensagem"]] = relationship(back_populates="conversa", order_by="Mensagem.created_at")
    pedidos: Mapped[list["Pedido"]] = relationship(back_populates="conversa")

    @property
    def cliente_nome(self) -> str:
        return self.cliente.nome

class Mensagem(Base):
    __tablename__ = "mensagens"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversa_id: Mapped[int] = mapped_column(ForeignKey("conversas.id"))
    origem: Mapped[str] = mapped_column(String(20))
    texto: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    conversa: Mapped["Conversa"] = relationship(back_populates="mensagens")

class Pedido(Base):
    __tablename__ = "pedidos"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversa_id: Mapped[int] = mapped_column(ForeignKey("conversas.id"))
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id"))
    empresa_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    itens_json: Mapped[str] = mapped_column(Text)
    valor_total: Mapped[float] = mapped_column(Float)
    origem: Mapped[PedidoOrigem] = mapped_column(Enum(PedidoOrigem))
    status: Mapped[PedidoStatus] = mapped_column(Enum(PedidoStatus), default=PedidoStatus.aguardando)
    metodo_pagamento: Mapped[str | None] = mapped_column(String(20), default=None)
    pago: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    link_pagamento: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    conversa: Mapped["Conversa"] = relationship(back_populates="pedidos")
    cliente: Mapped["Cliente"] = relationship()

    @property
    def cliente_nome(self) -> str:
        return self.cliente.nome

class Empresa(Base):
    __tablename__ = "empresas"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(200))
    cnpj: Mapped[str | None] = mapped_column(String(18), default=None)
    cidade: Mapped[str | None] = mapped_column(String(100), default=None)
    plano: Mapped[str] = mapped_column(String(20), nullable=False, default="starter")
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    whatsapp_numero: Mapped[str | None] = mapped_column(String(20), default=None)
    evolution_url: Mapped[str | None] = mapped_column(Text, default=None)
    evolution_instance: Mapped[str | None] = mapped_column(String(100), default=None)
    whatsapp_conectado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    email_contato: Mapped[str | None] = mapped_column(String(200), default=None)
    telefone: Mapped[str | None] = mapped_column(String(40), default=None)
    endereco: Mapped[str | None] = mapped_column(Text, default=None)
    responsavel: Mapped[str | None] = mapped_column(String(200), default=None)
    segmento: Mapped[str | None] = mapped_column(String(40), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Usuario(Base):
    __tablename__ = "usuarios"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(200), unique=True)
    senha_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="empresa")
    empresa_id: Mapped[int | None] = mapped_column(Integer, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Vendedor(Base):
    __tablename__ = "vendedores"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(200), default=None)
    telefone: Mapped[str | None] = mapped_column(String(40), default=None)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    meta_mensal: Mapped[float | None] = mapped_column(Float, default=None)
    empresa_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Produto(Base):
    __tablename__ = "produtos"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(200))
    categoria: Mapped[str | None] = mapped_column(String(80))
    preco_kg: Mapped[float] = mapped_column(Float)
    sku: Mapped[str | None] = mapped_column(String(60), default=None)
    unidade: Mapped[str] = mapped_column(String(8), nullable=False, default="kg")
    estoque: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    estoque_minimo: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    preco_custo: Mapped[float | None] = mapped_column(Float, default=None)
    descricao: Mapped[str | None] = mapped_column(Text, default=None)
    empresa_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
