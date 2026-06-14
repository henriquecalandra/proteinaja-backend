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
    ativo: Mapped[bool] = mapped_column(default=True)
    atendido_por_ia: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    conversas: Mapped[list["Conversa"]] = relationship(back_populates="cliente")

class Conversa(Base):
    __tablename__ = "conversas"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id"))
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

class Usuario(Base):
    __tablename__ = "usuarios"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(200), unique=True)
    senha_hash: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Produto(Base):
    __tablename__ = "produtos"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(200), unique=True)
    categoria: Mapped[str | None] = mapped_column(String(80))
    preco_kg: Mapped[float] = mapped_column(Float)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
