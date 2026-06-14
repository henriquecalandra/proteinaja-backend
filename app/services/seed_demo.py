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

# Whatsapp que marca a presenca do seed da 2a empresa (Boi Dourado).
MARKER_WHATSAPP_EMPRESA2 = "5565992220001"

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


def _seed_produtos(db: Session, empresa_id: int | None = None) -> None:
    """Popula o catalogo de produtos a partir de PRECOS, de forma idempotente.

    Insere apenas os produtos que ainda nao existem (por nome) NA EMPRESA dada.
    Os produtos sao por empresa agora (multi-tenant), entao a checagem de
    existencia e por (nome, empresa_id). Roda tanto no seed novo quanto no
    early-return, para popular catalogo em bancos ja semeados.
    """
    try:
        existentes = {
            nome
            for (nome,) in db.query(Produto.nome)
            .filter(Produto.empresa_id == empresa_id)
            .all()
        }
        novos = 0
        for nome, preco in PRECOS.items():
            if nome in existentes:
                continue
            db.add(
                Produto(
                    nome=nome,
                    categoria=CATEGORIAS.get(nome),
                    preco_kg=preco,
                    empresa_id=empresa_id,
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


EMPRESA_SECUNDARIA_NOME = "Frigorifico Boi Dourado"


def _empresa_principal_id(db: Session) -> int | None:
    """Retorna o id da empresa principal (Sao Lucas), se existir."""
    principal = (
        db.query(Empresa).filter(Empresa.nome == EMPRESA_PRINCIPAL_NOME).first()
    )
    return principal.id if principal else None


def _backfill_empresa_principal(db: Session, empresa_id: int) -> None:
    """Atribui empresa_id da principal aos dados legados (empresa_id IS NULL).

    Idempotente: so afeta linhas com empresa_id NULL. Cobre clientes, produtos,
    conversas e pedidos. Defensivo: nunca derruba o startup.
    """
    if not empresa_id:
        return
    try:
        total = 0
        for Model in (Cliente, Produto, Conversa, Pedido):
            total += (
                db.query(Model)
                .filter(Model.empresa_id.is_(None))
                .update({Model.empresa_id: empresa_id}, synchronize_session=False)
            )
        if total:
            db.commit()
            logger.info(
                "seed_demo: backfill empresa_id=%s em %d linhas legadas",
                empresa_id,
                total,
            )
    except Exception:
        logger.exception("seed_demo: falha no backfill de empresa_id (ignorado)")
        try:
            db.rollback()
        except Exception:
            pass


def _seed_multitenant(db: Session) -> int | None:
    """Cria empresas, usuario admin e vincula o marcos. Idempotente e defensivo.

    Retorna o id da empresa principal (Sao Lucas) ou None em caso de falha.
    """
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

        # 5) Usuario da 2a empresa (joao@boidourado.com) vinculado a Boi Dourado.
        secundaria = (
            db.query(Empresa)
            .filter(Empresa.nome == EMPRESA_SECUNDARIA_NOME)
            .first()
        )
        if secundaria:
            joao = (
                db.query(Usuario)
                .filter(Usuario.email == "joao@boidourado.com")
                .first()
            )
            if not joao:
                db.add(
                    Usuario(
                        nome="Joao Boi Dourado",
                        email="joao@boidourado.com",
                        senha_hash=hash_senha("senha123"),
                        role="empresa",
                        empresa_id=secundaria.id,
                    )
                )
            else:
                db.query(Usuario).filter(
                    Usuario.email == "joao@boidourado.com"
                ).update(
                    {Usuario.role: "empresa", Usuario.empresa_id: secundaria.id},
                    synchronize_session=False,
                )
            db.commit()

        logger.info("seed_demo: camada multi-tenant garantida")
        return principal.id if principal else None
    except Exception:
        logger.exception("seed_demo: falha ao semear multi-tenant (ignorado)")
        try:
            db.rollback()
        except Exception:
            pass
        return None


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


# Clientes proprios da 2a empresa (Boi Dourado). (nome, cnpj, whatsapp, tipo, cidade)
CLIENTES_EMPRESA2 = [
    ("Acougue do Cuiaba", "13.131.313/0001-13", MARKER_WHATSAPP_EMPRESA2, ClienteTipo.acougue, "Cuiaba"),
    ("Restaurante Pantanal", "14.141.414/0001-14", "5565992220002", ClienteTipo.restaurante, "Cuiaba"),
    ("Mercado Bom Preco MT", "15.151.515/0001-15", "5565992220003", ClienteTipo.mercadinho, "Varzea Grande"),
]


def _seed_empresa2(db: Session, empresa_id: int) -> None:
    """Cria dados PROPRIOS da 2a empresa (Boi Dourado). Idempotente e defensivo.

    Cria ~3 clientes, ~5 produtos, ~4 pedidos (alguns hoje) e 2 conversas com
    mensagens, TODOS com empresa_id da 2a empresa. Idempotente via cliente
    marcador (MARKER_WHATSAPP_EMPRESA2).
    """
    if not empresa_id:
        return
    try:
        # Produtos proprios da empresa 2 (~5). Idempotente por (nome, empresa_id).
        prod_empresa2 = ["Picanha", "Costela bovina", "Fraldinha", "Frango inteiro", "Carne moida"]
        existentes_p = {
            nome
            for (nome,) in db.query(Produto.nome)
            .filter(Produto.empresa_id == empresa_id)
            .all()
        }
        for nome in prod_empresa2:
            if nome in existentes_p:
                continue
            db.add(
                Produto(
                    nome=nome,
                    categoria=CATEGORIAS.get(nome),
                    preco_kg=PRECOS[nome],
                    empresa_id=empresa_id,
                    ativo=True,
                )
            )
        db.commit()

        # Idempotencia dos dados transacionais: cliente marcador da empresa 2.
        if db.query(Cliente).filter(Cliente.whatsapp == MARKER_WHATSAPP_EMPRESA2).first():
            logger.info("seed_demo: dados da 2a empresa ja existem")
            return

        # Clientes (~3).
        clientes2: list[Cliente] = []
        for nome, cnpj, whats, tipo, cidade in CLIENTES_EMPRESA2:
            c = Cliente(
                nome=nome,
                cnpj=cnpj,
                whatsapp=whats,
                tipo=tipo,
                cidade=cidade,
                empresa_id=empresa_id,
                ativo=True,
                created_at=_dias_atras(15),
            )
            db.add(c)
            clientes2.append(c)
        db.flush()

        # Conversas (2) com mensagens.
        convs2: list[Conversa] = []
        spec_conv = [
            (0, DIALOGO_PEDIDO_IA, ConversaStatus.agente, _hoje_em(10, 0)),
            (1, DIALOGO_NEGOCIANDO, ConversaStatus.humano, _hoje_em(14, 0)),
        ]
        for idx, dialogo, statusc, dt in spec_conv:
            conv = Conversa(
                cliente_id=clientes2[idx].id,
                empresa_id=empresa_id,
                status=statusc,
                created_at=dt,
                updated_at=dt + timedelta(minutes=20),
            )
            db.add(conv)
            db.flush()
            _add_mensagens(db, conv, dialogo, dt)
            convs2.append(conv)

        # Pedidos (~4), alguns hoje.
        ij = _itens
        i_a, v_a = ij(("Picanha", 10), ("Fraldinha", 8))
        i_b, v_b = ij(("Costela bovina", 20))
        i_c, v_c = ij(("Frango inteiro", 25))
        i_d, v_d = ij(("Carne moida", 18))
        spec_ped = [
            (0, i_a, v_a, PedidoOrigem.ia, PedidoStatus.confirmado, _hoje_em(10, 30)),
            (0, i_c, v_c, PedidoOrigem.ia, PedidoStatus.confirmado, _hoje_em(11, 0)),
            (1, i_b, v_b, PedidoOrigem.humano, PedidoStatus.aguardando, _hoje_em(14, 30)),
            (1, i_d, v_d, PedidoOrigem.ia, PedidoStatus.entregue, _dias_atras(3, 12)),
        ]
        for conv_idx, itens_json, valor, origem, statusp, dt in spec_ped:
            conv = convs2[conv_idx]
            db.add(
                Pedido(
                    conversa_id=conv.id,
                    cliente_id=conv.cliente_id,
                    empresa_id=empresa_id,
                    itens_json=itens_json,
                    valor_total=valor,
                    origem=origem,
                    status=statusp,
                    created_at=dt,
                )
            )
        db.commit()
        logger.info(
            "seed_demo: 2a empresa (id=%s) semeada: %d clientes, %d conversas, %d pedidos",
            empresa_id,
            len(clientes2),
            len(convs2),
            len(spec_ped),
        )
    except Exception:
        logger.exception("seed_demo: falha ao semear 2a empresa (ignorado)")
        try:
            db.rollback()
        except Exception:
            pass


def seed_demo(db: Session) -> None:
    """Popula o banco com dados de demonstracao. Idempotente e defensivo."""
    try:
        # 1) Limpeza dos dados de QA (sempre, mesmo se o seed ja existir).
        _limpar_qa(db)

        # 2) Idempotencia: se o cliente marcador ja existe, nao recria nada.
        #    Mas a marcacao de clientes manuais roda SEMPRE (idempotente).
        if db.query(Cliente).filter(Cliente.whatsapp == MARKER_WHATSAPP).first():
            _marcar_clientes_manuais(db)
            # Camada multi-tenant primeiro: garante empresas/usuarios e nos da o
            # id da empresa principal para backfill e catalogo.
            principal_id = _seed_multitenant(db)
            if principal_id:
                _backfill_empresa_principal(db, principal_id)
                _seed_produtos(db, principal_id)
                secundaria = (
                    db.query(Empresa)
                    .filter(Empresa.nome == EMPRESA_SECUNDARIA_NOME)
                    .first()
                )
                if secundaria:
                    _seed_empresa2(db, secundaria.id)
            else:
                _seed_produtos(db)
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

        # 7) Camada multi-tenant (empresas, admin, vinculo do marcos e joao).
        principal_id = _seed_multitenant(db)

        # 8) Backfill: dados recem-criados (empresa_id NULL) viram da principal,
        #    catalogo da principal e dados proprios da 2a empresa.
        if principal_id:
            _backfill_empresa_principal(db, principal_id)
            _seed_produtos(db, principal_id)
            secundaria = (
                db.query(Empresa)
                .filter(Empresa.nome == EMPRESA_SECUNDARIA_NOME)
                .first()
            )
            if secundaria:
                _seed_empresa2(db, secundaria.id)
        else:
            _seed_produtos(db)

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
