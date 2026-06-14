from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import (
    Cliente,
    Conversa,
    Mensagem,
    Pedido,
    Produto,
    Empresa,
    ConversaStatus,
    ClienteTipo,
    PedidoOrigem,
    PedidoStatus,
)
from app.services.agent import gerar_resposta, deve_escalar_para_humano, extrair_pedido
from app.services.whatsapp import enviar_mensagem
import asyncio
import json
import logging

logger = logging.getLogger("webhook")

router = APIRouter(prefix="/webhook", tags=["webhook"])

# Nome da empresa principal (WhatsApp simulado, sem roteamento por instancia).
EMPRESA_PRINCIPAL_NOME = "Frigorifico Sao Lucas"


def _empresa_principal_id(db: Session) -> int | None:
    """Resolve o id da empresa principal (Sao Lucas). Defensivo: None se falhar."""
    try:
        empresa = (
            db.query(Empresa).filter(Empresa.nome == EMPRESA_PRINCIPAL_NOME).first()
        )
        return empresa.id if empresa else None
    except Exception:
        return None


def obter_ou_criar_cliente(db: Session, numero: str, nome: str, empresa_id: int | None = None) -> Cliente:
    cliente = db.query(Cliente).filter(Cliente.whatsapp == numero).first()
    if not cliente:
        cliente = Cliente(nome=nome or numero, whatsapp=numero, tipo=ClienteTipo.acougue, empresa_id=empresa_id)
        db.add(cliente)
        db.commit()
        db.refresh(cliente)
    return cliente

def obter_ou_criar_conversa(db: Session, cliente_id: int, empresa_id: int | None = None) -> Conversa:
    conversa = (
        db.query(Conversa)
        .filter(Conversa.cliente_id == cliente_id, Conversa.status != ConversaStatus.encerrada)
        .order_by(Conversa.updated_at.desc())
        .first()
    )
    if not conversa:
        conversa = Conversa(cliente_id=cliente_id, empresa_id=empresa_id)
        db.add(conversa)
        db.commit()
        db.refresh(conversa)
    return conversa

@router.post("/whatsapp")
async def receber_mensagem(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    event = body.get("event", "")
    if event != "messages.upsert":
        return {"ok": True}

    data = body.get("data", {})
    key = data.get("key", {})

    if key.get("fromMe", False):
        return {"ok": True}

    numero = key.get("remoteJid", "").replace("@s.whatsapp.net", "")
    texto = data.get("message", {}).get("conversation", "") or \
            data.get("message", {}).get("extendedTextMessage", {}).get("text", "")
    nome_push = data.get("pushName", "")

    if not numero or not texto:
        return {"ok": True}

    empresa_id = _empresa_principal_id(db)
    cliente = obter_ou_criar_cliente(db, numero, nome_push, empresa_id)
    conversa = obter_ou_criar_conversa(db, cliente.id, empresa_id)

    if conversa.status == ConversaStatus.humano:
        msg = Mensagem(conversa_id=conversa.id, origem="cliente", texto=texto)
        db.add(msg)
        db.commit()
        return {"ok": True}

    # Cliente marcado como atendimento manual: NAO chama a IA.
    # Salva a mensagem, marca a conversa como humano e retorna.
    if not cliente.atendido_por_ia:
        msg = Mensagem(conversa_id=conversa.id, origem="cliente", texto=texto)
        db.add(msg)
        conversa.status = ConversaStatus.humano
        db.commit()
        return {"ok": True}

    msg_cliente = Mensagem(conversa_id=conversa.id, origem="cliente", texto=texto)
    db.add(msg_cliente)
    db.commit()

    historico = db.query(Mensagem).filter(Mensagem.conversa_id == conversa.id).all()

    # Consulta os produtos ativos para passar a tabela de precos real ao agente.
    # Defensivo: se a tabela estiver vazia ou falhar, o agente usa o catalogo padrao.
    try:
        produtos_q = db.query(Produto).filter(Produto.ativo.is_(True))
        if empresa_id is not None:
            produtos_q = produtos_q.filter(Produto.empresa_id == empresa_id)
        produtos = [
            (p.nome, p.preco_kg)
            for p in produtos_q.order_by(Produto.nome).all()
        ]
    except Exception:
        produtos = None

    resposta = gerar_resposta(texto, historico[:-1], cliente, produtos=produtos)

    if deve_escalar_para_humano(resposta):
        conversa.status = ConversaStatus.humano
        db.add(Mensagem(conversa_id=conversa.id, origem="sistema",
                        texto="⚠ Agente escalou para atendimento humano"))

    msg_agente = Mensagem(conversa_id=conversa.id, origem="agente", texto=resposta)
    db.add(msg_agente)
    db.commit()

    # Extracao automatica de pedido pela IA. TOTALMENTE DEFENSIVO: nunca pode
    # quebrar o webhook. extrair_pedido retorna [] quando nao ha pedido fechado
    # (o que evita criar/duplicar pedidos).
    try:
        itens_extraidos = extrair_pedido(historico, texto, produtos=produtos)
        if itens_extraidos:
            # Mapa nome (lower) -> Produto ativo do catalogo, para obter preco_kg.
            catalogo_q = db.query(Produto).filter(Produto.ativo.is_(True))
            if empresa_id is not None:
                catalogo_q = catalogo_q.filter(Produto.empresa_id == empresa_id)
            catalogo = {
                p.nome.lower(): p
                for p in catalogo_q.all()
            }
            itens_pedido = []
            valor_total = 0.0
            for item in itens_extraidos:
                nome = str(item.get("produto", "")).strip()
                try:
                    qtd = float(item.get("qtd_kg"))
                except (TypeError, ValueError):
                    continue
                if not nome or qtd <= 0:
                    continue
                produto = catalogo.get(nome.lower())
                if produto is None:
                    continue
                preco = float(produto.preco_kg)
                itens_pedido.append(
                    {"produto": produto.nome, "qtd_kg": qtd, "preco_kg": preco}
                )
                valor_total += qtd * preco
            if itens_pedido:
                pedido = Pedido(
                    conversa_id=conversa.id,
                    cliente_id=cliente.id,
                    empresa_id=empresa_id,
                    itens_json=json.dumps(itens_pedido, ensure_ascii=False),
                    valor_total=valor_total,
                    origem=PedidoOrigem.ia,
                    status=PedidoStatus.confirmado,
                )
                db.add(pedido)
                db.commit()
    except Exception:
        logger.exception("webhook: falha ao extrair/criar pedido pela IA (ignorado)")
        try:
            db.rollback()
        except Exception:
            pass

    try:
        asyncio.create_task(enviar_mensagem(numero, resposta))
    except RuntimeError:
        # No running event loop in test context; skip background task
        pass
    return {"ok": True}
