from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Cliente, Conversa, Mensagem, Produto, ConversaStatus, ClienteTipo
from app.services.agent import gerar_resposta, deve_escalar_para_humano
from app.services.whatsapp import enviar_mensagem
import asyncio

router = APIRouter(prefix="/webhook", tags=["webhook"])

def obter_ou_criar_cliente(db: Session, numero: str, nome: str) -> Cliente:
    cliente = db.query(Cliente).filter(Cliente.whatsapp == numero).first()
    if not cliente:
        cliente = Cliente(nome=nome or numero, whatsapp=numero, tipo=ClienteTipo.acougue)
        db.add(cliente)
        db.commit()
        db.refresh(cliente)
    return cliente

def obter_ou_criar_conversa(db: Session, cliente_id: int) -> Conversa:
    conversa = (
        db.query(Conversa)
        .filter(Conversa.cliente_id == cliente_id, Conversa.status != ConversaStatus.encerrada)
        .order_by(Conversa.updated_at.desc())
        .first()
    )
    if not conversa:
        conversa = Conversa(cliente_id=cliente_id)
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

    cliente = obter_ou_criar_cliente(db, numero, nome_push)
    conversa = obter_ou_criar_conversa(db, cliente.id)

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
        produtos = [
            (p.nome, p.preco_kg)
            for p in db.query(Produto).filter(Produto.ativo.is_(True)).order_by(Produto.nome).all()
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

    try:
        asyncio.create_task(enviar_mensagem(numero, resposta))
    except RuntimeError:
        # No running event loop in test context; skip background task
        pass
    return {"ok": True}
