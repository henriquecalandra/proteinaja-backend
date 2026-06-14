"""
Seed de dados de demonstracao para a apresentacao academica do ProteinaJa.

Gera clientes, conversas, mensagens e pedidos realistas do setor de proteina
(Frigorifico Sao Lucas - Goias). Tudo defensivo e idempotente: pode rodar a
cada startup sem duplicar dados e sem derrubar o app.

Pontos importantes:
- IDEMPOTENTE: usa um cliente "marcador" (whatsapp conhecido) para detectar se o
  seed ja rodou. Se existir, nao recria nada.
- LIMPEZA QA: remove o cliente de teste 5562988887777 e seus dados associados.
- DASHBOARD: garante varios pedidos/conversas com created_at = HOJE (UTC), a
  maioria com origem 'ia', para popular pedidos_hoje / volume_hoje.
"""

import json
import logging
import random
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import (
    Cliente,
    Conversa,
    Mensagem,
    Pedido,
    Produto,
    Empresa,
    Usuario,
    ClienteTipo,
    ConversaStatus,
    PedidoStatus,
    PedidoOrigem,
)

logger = logging.getLogger("seed_demo")

# Whatsapp que marca a presenca do seed de demonstracao.
# Se este cliente existir, assumimos que o seed ja foi aplicado.
MARKER_WHATSAPP = "5562991110001"

# Cliente de teste de QA que deve ser removido junto com seus dados.
QA_WHATSAPP = "5562988887777"

# Clientes de demo que devem aparecer como atendimento MANUAL (atendido_por_ia=False),
# para a demo mostrar a diferenca entre clientes "Manual" e "IA".
MANUAL_WHATSAPPS = ["5564991110004", "5562991110008", "5562991110009"]

# Tabela de precos de referencia (R$/kg) para gerar valores coerentes.
PRECOS = {
    "Picanha": 64.90,
    "Alcatra": 42.50,
    "Costela bovina": 32.90,
    "Coxao mole": 38.90,
    "Coxao duro": 34.50,
    "Patinho": 37.90,
    "Acem": 28.90,
    "Fraldinha": 45.90,
    "Maminha": 44.50,
    "File mignon": 79.90,
    "Contra file": 49.90,
    "Cupim": 39.90,
    "Linguica toscana": 24.90,
    "Linguica calabresa": 26.90,
    "Frango inteiro": 12.90,
    "Peito de frango": 18.90,
    "Coxa e sobrecoxa": 13.90,
    "Pernil suino": 22.90,
    "Costela suina": 27.90,
    "Carne moida": 29.90,
}

# Categoria de cada produto do catalogo (para o catalogo de produtos).
CATEGORIAS = {
    "Picanha": "Bovino",
    "Alcatra": "Bovino",
    "Costela bovina": "Bovino",
    "Coxao mole": "Bovino",
    "Coxao duro": "Bovino",
    "Patinho": "Bovino",
    "Acem": "Bovino",
    "Fraldinha": "Bovino",
    "Maminha": "Bovino",
    "File mignon": "Bovino",
    "Contra file": "Bovino",
    "Cupim": "Bovino",
    "Carne moida": "Bovino",
    "Pernil suino": "Suino",
    "Costela suina": "Suino",
    "Frango inteiro": "Aves",
    "Peito de frango": "Aves",
    "Coxa e sobrecoxa": "Aves",
    "Linguica toscana": "Embutidos",
    "Linguica calabresa": "Embutidos",
}


def _seed_produtos(db: Session) -> None:
    """Popula o catalogo de produtos a partir de PRECOS, de forma idempotente.

    Insere apenas os produtos que ainda nao existem (por nome). Roda tanto no
    seed novo quanto no early-return, para popular catalogo em bancos ja semeados.
    """
    try:
        existentes = {nome for (nome,) in db.query(Produto.nome).all()}
        novos = 0
        for nome, preco in PRECOS.items():
            if nome in existentes:
                continue
            db.add(
                Produto(
                    nome=nome,
                    categoria=CATEGORIAS.get(nome),
                    preco_kg=preco,
                    ativo=True,
                )
            )
            novos += 1
        if novos:
            db.commit()
            logger.info("seed_demo: %d produtos criados no catalogo", novos)
    except Exception:
        logger.exception("seed_demo: falha ao popular catalogo de produtos (ignorado)")
        try:
            db.rollback()
        except Exception:
            pass


def _itens(*pares):
    """Monta lista de itens (produto, qtd_kg) -> dicts com preco_kg.

    Retorna (itens_json_str, valor_total_float).
    """
    itens = []
    total = 0.0
    for produto, qtd_kg in pares:
        preco_kg = PRECOS[produto]
        itens.append({"produto": produto, "qtd_kg": qtd_kg, "preco_kg": preco_kg})
        total += qtd_kg * preco_kg
    return json.dumps(itens, ensure_ascii=False), round(total, 2)


def _hoje_em(hora: int, minuto: int = 0) -> datetime:
    """Datetime de HOJE (UTC) em uma hora especifica, sem virar de dia.

    Mantemos a hora entre 0 e 23 para garantir que a data UTC permaneca a de
    hoje, ja que o dashboard agrupa por data UTC.
    """
    agora = datetime.utcnow()
    hora = max(0, min(23, hora))
    return agora.replace(hour=hora, minute=minuto, second=0, microsecond=0)


def _dias_atras(dias: int, hora: int = 10, minuto: int = 0) -> datetime:
    base = datetime.utcnow() - timedelta(days=dias)
    return base.replace(hour=hora, minute=minuto, second=0, microsecond=0)


def _limpar_qa(db: Session) -> None:
    """Remove o cliente de teste de QA e todos os dados associados."""
    qa = db.query(Cliente).filter(Cliente.whatsapp == QA_WHATSAPP).first()
    if not qa:
        return
    conversas = db.query(Conversa).filter(Conversa.cliente_id == qa.id).all()
    conv_ids = [c.id for c in conversas]
    if conv_ids:
        db.query(Mensagem).filter(Mensagem.conversa_id.in_(conv_ids)).delete(
            synchronize_session=False
        )
    db.query(Pedido).filter(Pedido.cliente_id == qa.id).delete(
        synchronize_session=False
    )
    if conv_ids:
        db.query(Conversa).filter(Conversa.id.in_(conv_ids)).delete(
            synchronize_session=False
        )
    db.delete(qa)
    db.commit()
    logger.info("seed_demo: cliente de QA %s removido", QA_WHATSAPP)


def _marcar_clientes_manuais(db: Session) -> None:
    """Garante que alguns clientes de demo sejam atendimento manual (IA off).

    Idempotente: roda sempre (mesmo se o seed ja existir) e so atualiza quem
    ainda nao esta marcado.
    """
    try:
        atualizados = (
            db.query(Cliente)
            .filter(
                Cliente.whatsapp.in_(MANUAL_WHATSAPPS),
                Cliente.atendido_por_ia.is_(True),
            )
            .update({Cliente.atendido_por_ia: False}, synchronize_session=False)
        )
        if atualizados:
            db.commit()
            logger.info("seed_demo: %d clientes marcados como manuais", atualizados)
    except Exception:
        logger.exception("seed_demo: falha ao marcar clientes manuais (ignorado)")
        try:
            db.rollback()
        except Exception:
            pass


# Definicao declarativa dos clientes de demonstracao.
# (nome, cnpj, whatsapp, tipo, cidade)
CLIENTES = [
    ("Acougue Boi Gordo", "12.345.678/0001-90", MARKER_WHATSAPP, ClienteTipo.acougue, "Goiania"),
    ("Restaurante Sabor do Cerrado", "23.456.789/0001-01", "5562991110002", ClienteTipo.restaurante, "Goiania"),
    ("Mercadinho Sao Jose", "34.567.890/0001-12", "5562991110003", ClienteTipo.mercadinho, "Anapolis"),
    ("Churrascaria Fogo Nativo", "45.678.901/0001-23", "5564991110004", ClienteTipo.restaurante, "Rio Verde"),
    ("Acougue Central da Carne", "56.789.012/0001-34", "5562991110005", ClienteTipo.acougue, "Aparecida de Goiania"),
    ("Cozinha Industrial Pratus", "67.890.123/0001-45", "5562991110006", ClienteTipo.food_service, "Goiania"),
    ("Supermercado Pague Pouco", "78.901.234/0001-56", "5564991110007", ClienteTipo.mercadinho, "Itumbiara"),
    ("Espetinho do Tiao", "89.012.345/0001-67", "5562991110008", ClienteTipo.restaurante, "Trindade"),
    ("Acougue Dois Irmaos", "90.123.456/0001-78", "5562991110009", ClienteTipo.acougue, "Senador Canedo"),
    ("Buffet Festa & Cia", "01.234.567/0001-89", "5562991110010", ClienteTipo.food_service, "Goiania"),
]

# Roteiros de conversa por "tipo" de dialogo. Cada item: (origem, texto).
DIALOGO_PEDIDO_IA = [
    ("cliente", "Boa tarde! Vcs tem picanha disponivel pra essa semana?"),
    ("agente", "Boa tarde! Aqui e do Frigorifico Sao Lucas. Temos sim, picanha resfriada a R$ 64,90 o kg. Quantos kg vc precisa?"),
    ("cliente", "Me ve uns 15kg de picanha e 10kg de alcatra"),
    ("agente", "Fechado! 15kg de picanha (R$ 64,90/kg) e 10kg de alcatra (R$ 42,50/kg). Total fica R$ 1.398,50. Entrega pra amanha de manha, pode ser?"),
    ("cliente", "Pode sim, amanha cedo ta otimo"),
    ("agente", "Perfeito! Pedido confirmado e ja anotado pra entrega amanha cedo. Qualquer coisa e so chamar!"),
]

DIALOGO_NEGOCIANDO = [
    ("cliente", "Bom dia, qto ta a costela hoje?"),
    ("agente", "Bom dia! Costela bovina ta R$ 32,90 o kg hoje. Vai querer quanto?"),
    ("cliente", "Eita, mes passado tava 29. Faz por 30 que fecho 40kg"),
    ("agente", "Entendo! Pra 40kg consigo fazer R$ 31,50 o kg. Topa? Sai R$ 1.260,00 no total."),
    ("cliente", "Deixa eu ver aqui com meu socio e ja te falo"),
    ("agente", "Tranquilo! Fico no aguardo. Esse valor seguro pra vc ate amanha."),
]

DIALOGO_FRANGO_IA = [
    ("cliente", "Oi, preciso repor o frango. Tem frango inteiro e coxa/sobrecoxa?"),
    ("agente", "Oi! Temos sim. Frango inteiro R$ 12,90/kg e coxa e sobrecoxa R$ 13,90/kg. Quanto de cada?"),
    ("cliente", "30kg de frango inteiro e 20kg de coxa e sobrecoxa"),
    ("agente", "Anotado! 30kg de frango inteiro + 20kg de coxa e sobrecoxa = R$ 665,00. Confirmo a entrega?"),
    ("cliente", "Confirma!"),
    ("agente", "Show! Pedido confirmado. Obrigado pela preferencia."),
]

DIALOGO_HUMANO = [
    ("cliente", "Preciso de um orcamento grande pra um evento de 300 pessoas, da pra falar com alguem?"),
    ("agente", "Claro! Vou te passar pro nosso atendimento comercial pra montar o orcamento certinho do evento."),
    ("sistema", "Conversa transferida para atendimento humano."),
    ("agente", "Oi, aqui e o Marcos do comercial. Me conta o cardapio que vc pensou que eu monto o pacote com desconto."),
    ("cliente", "Vai ter churrasco, entao picanha, fraldinha, linguica e frango"),
]

DIALOGO_ENCERRADA = [
    ("cliente", "Recebi o pedido hoje, veio tudo certinho. Valeu!"),
    ("agente", "Que otimo! Ficamos felizes. Qualquer coisa estamos a disposicao. Bom trabalho!"),
    ("sistema", "Conversa encerrada pelo atendente."),
]

DIALOGO_SUINO_IA = [
    ("cliente", "Boa! Tem pernil e costela suina?"),
    ("agente", "Boa! Pernil suino R$ 22,90/kg e costela suina R$ 27,90/kg. Quanto vc quer?"),
    ("cliente", "12kg de pernil e 8kg de costela suina"),
    ("agente", "Fechado! 12kg de pernil + 8kg de costela suina = R$ 497,40. Entrego junto com o proximo carregamento da sua regiao."),
    ("cliente", "Beleza, obrigado"),
    ("agente", "Por nada! Pedido confirmado."),
]


# Empresa principal (a do Frigorifico Sao Lucas, dono do marcos).
EMPRESA_PRINCIPAL_NOME = "Frigorifico Sao Lucas"

# Empresas de demonstracao (white-label). (nome, cnpj, cidade, plano, ativo)
EMPRESAS_DEMO = [
    ("Frigorifico Boi Dourado", "11.111.111/0001-11", "Cuiaba", "pro", True),
    ("Frigorifico Vale Verde", "22.222.222/0001-22", "Uberlandia", "starter", True),
    ("Frigorifico Pampa Sul", "33.333.333/0001-33", "Pelotas", "enterprise", True),
    ("Frigorifico Serra Nevada", "44.444.444/0001-44", "Caxias do Sul", "starter", False),
    ("Frigorifico Norte Carnes", "55.555.555/0001-55", "Maraba", "pro", True),
]


def _seed_multitenant(db: Session) -> None:
    """Cria empresas, usuario admin e vincula o marcos. Idempotente e defensivo."""
    try:
        from app.services.auth import hash_senha

        # 1) Empresa principal (idempotente por nome).
        principal = (
            db.query(Empresa)
            .filter(Empresa.nome == EMPRESA_PRINCIPAL_NOME)
            .first()
        )
        if not principal:
            principal = Empresa(
                nome=EMPRESA_PRINCIPAL_NOME,
                cnpj="00.000.000/0001-00",
                cidade="Goias",
                plano="pro",
                ativo=True,
                whatsapp_numero="5562990001234",
                whatsapp_conectado=False,
            )
            db.add(principal)
            db.flush()

        # 2) Empresas de demo (idempotente por nome).
        for nome, cnpj, cidade, plano, ativo in EMPRESAS_DEMO:
            if not db.query(Empresa).filter(Empresa.nome == nome).first():
                db.add(
                    Empresa(
                        nome=nome,
                        cnpj=cnpj,
                        cidade=cidade,
                        plano=plano,
                        ativo=ativo,
                        whatsapp_conectado=False,
                    )
                )

        # 3) Usuario admin (idempotente por email).
        admin = db.query(Usuario).filter(Usuario.email == "admin@proteinaja.com").first()
        if not admin:
            db.add(
                Usuario(
                    nome="Administrador ProteinaJa",
                    email="admin@proteinaja.com",
                    senha_hash=hash_senha("admin123"),
                    role="admin",
                    empresa_id=None,
                )
            )

        db.commit()

        # 4) Atualiza marcos: role='empresa', empresa_id = id da empresa principal.
        principal = (
            db.query(Empresa)
            .filter(Empresa.nome == EMPRESA_PRINCIPAL_NOME)
            .first()
        )
        if principal:
            db.query(Usuario).filter(Usuario.email == "marcos@frigorifico.com").update(
                {Usuario.role: "empresa", Usuario.empresa_id: principal.id},
                synchronize_session=False,
            )
            db.commit()

        logger.info("seed_demo: camada multi-tenant garantida")
    except Exception:
        logger.exception("seed_demo: falha ao semear multi-tenant (ignorado)")
        try:
            db.rollback()
        except Exception:
            pass


def _add_mensagens(db: Session, conversa: Conversa, dialogo, base_dt: datetime) -> None:
    """Adiciona mensagens do dialogo espacadas em minutos a partir de base_dt."""
    for i, (origem, texto) in enumerate(dialogo):
        ts = base_dt + timedelta(minutes=2 * i)
        db.add(
            Mensagem(
                conversa_id=conversa.id,
                origem=origem,
                texto=texto,
                created_at=ts,
            )
        )


def seed_demo(db: Session) -> None:
    """Popula o banco com dados de demonstracao. Idempotente e defensivo."""
    try:
        # 1) Limpeza dos dados de QA (sempre, mesmo se o seed ja existir).
        _limpar_qa(db)

        # 2) Idempotencia: se o cliente marcador ja existe, nao recria nada.
        #    Mas a marcacao de clientes manuais roda SEMPRE (idempotente).
        if db.query(Cliente).filter(Cliente.whatsapp == MARKER_WHATSAPP).first():
            _marcar_clientes_manuais(db)
            _seed_produtos(db)
            _seed_multitenant(db)
            logger.info("seed_demo: dados de demo ja existem, catalogo garantido")
            return

        random.seed(42)  # reprodutibilidade

        # 3) Criar clientes.
        clientes_obj: dict[str, Cliente] = {}
        for nome, cnpj, whats, tipo, cidade in CLIENTES:
            c = Cliente(
                nome=nome,
                cnpj=cnpj,
                whatsapp=whats,
                tipo=tipo,
                cidade=cidade,
                ativo=True,
                created_at=_dias_atras(random.randint(20, 60)),
            )
            db.add(c)
            clientes_obj[whats] = c
        db.flush()  # garante IDs

        clist = list(clientes_obj.values())

        # 4) Criar conversas + mensagens.
        # (cliente_idx, dialogo, status, created_at)
        conversas_spec = [
            (0, DIALOGO_PEDIDO_IA, ConversaStatus.agente, _hoje_em(8, 15)),
            (1, DIALOGO_FRANGO_IA, ConversaStatus.agente, _hoje_em(9, 40)),
            (2, DIALOGO_NEGOCIANDO, ConversaStatus.agente, _hoje_em(11, 5)),
            (3, DIALOGO_HUMANO, ConversaStatus.humano, _hoje_em(13, 20)),
            (4, DIALOGO_SUINO_IA, ConversaStatus.agente, _hoje_em(15, 0)),
            (5, DIALOGO_PEDIDO_IA, ConversaStatus.agente, _hoje_em(16, 30)),
            (6, DIALOGO_NEGOCIANDO, ConversaStatus.humano, _dias_atras(1, 10)),
            (7, DIALOGO_FRANGO_IA, ConversaStatus.agente, _dias_atras(2, 14)),
            (8, DIALOGO_ENCERRADA, ConversaStatus.encerrada, _dias_atras(3, 9)),
            (9, DIALOGO_SUINO_IA, ConversaStatus.agente, _dias_atras(4, 16)),
            (0, DIALOGO_ENCERRADA, ConversaStatus.encerrada, _dias_atras(6, 11)),
            (2, DIALOGO_PEDIDO_IA, ConversaStatus.agente, _dias_atras(8, 13)),
            (4, DIALOGO_HUMANO, ConversaStatus.humano, _dias_atras(10, 15)),
            (5, DIALOGO_FRANGO_IA, ConversaStatus.encerrada, _dias_atras(12, 10)),
        ]

        conversas_obj: list[Conversa] = []
        for idx, dialogo, status, dt in conversas_spec:
            conv = Conversa(
                cliente_id=clist[idx].id,
                status=status,
                created_at=dt,
                updated_at=dt + timedelta(minutes=20),
            )
            db.add(conv)
            db.flush()
            _add_mensagens(db, conv, dialogo, dt)
            conversas_obj.append(conv)

        # 5) Criar pedidos. Garantimos varios HOJE com origem 'ia'.
        # (conversa_idx, itens, origem, status, created_at)
        ij = _itens  # alias

        i_picanha, v_picanha = ij(("Picanha", 15), ("Alcatra", 10))
        i_frango, v_frango = ij(("Frango inteiro", 30), ("Coxa e sobrecoxa", 20))
        i_costela, v_costela = ij(("Costela bovina", 40))
        i_suino, v_suino = ij(("Pernil suino", 12), ("Costela suina", 8))
        i_misto, v_misto = ij(("Fraldinha", 12), ("Linguica toscana", 10), ("Carne moida", 15))
        i_evento, v_evento = ij(("Picanha", 25), ("Fraldinha", 20), ("Linguica calabresa", 15), ("Peito de frango", 30))
        i_acem, v_acem = ij(("Acem", 20), ("Coxao mole", 12))
        i_premium, v_premium = ij(("File mignon", 8), ("Contra file", 10))
        i_cupim, v_cupim = ij(("Cupim", 10), ("Maminha", 8))
        i_moida, v_moida = ij(("Carne moida", 25), ("Patinho", 10))

        pedidos_spec = [
            # ---- HOJE (UTC) - maioria origem ia ----
            (0, i_picanha, v_picanha, PedidoOrigem.ia, PedidoStatus.confirmado, _hoje_em(8, 30)),
            (1, i_frango, v_frango, PedidoOrigem.ia, PedidoStatus.confirmado, _hoje_em(9, 55)),
            (4, i_suino, v_suino, PedidoOrigem.ia, PedidoStatus.confirmado, _hoje_em(15, 15)),
            (5, i_misto, v_misto, PedidoOrigem.ia, PedidoStatus.aguardando, _hoje_em(16, 45)),
            (2, i_costela, v_costela, PedidoOrigem.ia, PedidoStatus.negociando, _hoje_em(11, 25)),
            (1, i_acem, v_acem, PedidoOrigem.ia, PedidoStatus.confirmado, _hoje_em(10, 10)),
            (3, i_evento, v_evento, PedidoOrigem.humano, PedidoStatus.aguardando, _hoje_em(13, 50)),
            (0, i_moida, v_moida, PedidoOrigem.ia, PedidoStatus.confirmado, _hoje_em(17, 30)),
            # ---- ultimos dias ----
            (6, i_costela, v_costela, PedidoOrigem.humano, PedidoStatus.entregue, _dias_atras(1, 11)),
            (7, i_frango, v_frango, PedidoOrigem.ia, PedidoStatus.entregue, _dias_atras(2, 15)),
            (9, i_suino, v_suino, PedidoOrigem.ia, PedidoStatus.entregue, _dias_atras(4, 17)),
            (11, i_picanha, v_picanha, PedidoOrigem.ia, PedidoStatus.entregue, _dias_atras(8, 14)),
            (8, i_premium, v_premium, PedidoOrigem.ia, PedidoStatus.entregue, _dias_atras(3, 10)),
            (12, i_evento, v_evento, PedidoOrigem.humano, PedidoStatus.entregue, _dias_atras(10, 16)),
            (13, i_cupim, v_cupim, PedidoOrigem.ia, PedidoStatus.entregue, _dias_atras(12, 11)),
            (10, i_misto, v_misto, PedidoOrigem.ia, PedidoStatus.entregue, _dias_atras(6, 12)),
            (7, i_moida, v_moida, PedidoOrigem.ia, PedidoStatus.entregue, _dias_atras(2, 9)),
            (9, i_acem, v_acem, PedidoOrigem.ia, PedidoStatus.entregue, _dias_atras(5, 14)),
            (6, i_premium, v_premium, PedidoOrigem.humano, PedidoStatus.entregue, _dias_atras(7, 10)),
            (11, i_frango, v_frango, PedidoOrigem.ia, PedidoStatus.entregue, _dias_atras(9, 15)),
        ]

        for conv_idx, itens_json, valor, origem, status, dt in pedidos_spec:
            conv = conversas_obj[conv_idx]
            db.add(
                Pedido(
                    conversa_id=conv.id,
                    cliente_id=conv.cliente_id,
                    itens_json=itens_json,
                    valor_total=valor,
                    origem=origem,
                    status=status,
                    created_at=dt,
                )
            )

        db.commit()

        # 6) Marca alguns clientes como atendimento manual (idempotente).
        _marcar_clientes_manuais(db)

        # 7) Popula o catalogo de produtos (idempotente).
        _seed_produtos(db)

        # 8) Camada multi-tenant (empresas, admin, vinculo do marcos).
        _seed_multitenant(db)

        logger.info(
            "seed_demo: %d clientes, %d conversas, %d pedidos criados",
            len(clist),
            len(conversas_obj),
            len(pedidos_spec),
        )
    except Exception:  # nunca derruba o app
        logger.exception("seed_demo: falha ao popular dados de demo (ignorado)")
        try:
            db.rollback()
        except Exception:
            pass
