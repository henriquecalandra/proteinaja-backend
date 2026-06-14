"""Revisao adversarial: onboarding multi-tenant + cadastro empresa + analytics.

Roda com SQLite em arquivo temporario, stub de groq, e cobre:
- ensure_schema adiciona as 5 colunas em 'empresas' quando a tabela ja existe SEM elas
- register cria empresa+usuario; novo usuario ve a propria empresa em /company; 409 duplicado
- /dashboard/analytics ISOLADO (marcos != joao; admin agregado); parse defensivo; dias com 0
- PATCH /company aceita os 5 campos novos
"""
import sys
import os
import types
import json
import tempfile
import importlib
from datetime import datetime, timedelta

# --- stub groq antes de qualquer import do app ---
if "groq" not in sys.modules:
    groq_stub = types.ModuleType("groq")
    class _Groq:  # noqa
        def __init__(self, *a, **k):
            pass
    groq_stub.Groq = _Groq
    sys.modules["groq"] = groq_stub

# --- banco SQLite temporario isolado ---
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
DB_PATH = _tmp.name
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"

failures = []
checks = 0

def check(cond, msg):
    global checks
    checks += 1
    if not cond:
        failures.append(msg)
        print(f"FAIL: {msg}")
    else:
        print(f"ok: {msg}")


# =========================================================================
# PARTE 1: ensure_schema cria as 5 colunas quando 'empresas' existe SEM elas
# =========================================================================
from sqlalchemy import create_engine, text, inspect

eng = create_engine(f"sqlite:///{DB_PATH}")
with eng.begin() as conn:
    # tabela 'empresas' legada: SO as colunas antigas, sem os 5 campos novos
    conn.execute(text(
        "CREATE TABLE empresas ("
        "id INTEGER PRIMARY KEY, nome VARCHAR(200), cnpj VARCHAR(18), "
        "cidade VARCHAR(100), plano VARCHAR(20) NOT NULL DEFAULT 'starter', "
        "ativo BOOLEAN NOT NULL DEFAULT 1, whatsapp_numero VARCHAR(20), "
        "evolution_url TEXT, evolution_instance VARCHAR(100), "
        "whatsapp_conectado BOOLEAN NOT NULL DEFAULT 0, created_at DATETIME)"
    ))

cols_antes = {c["name"] for c in inspect(eng).get_columns("empresas")}
novos = {"email_contato", "telefone", "endereco", "responsavel", "segmento"}
check(novos.isdisjoint(cols_antes), "pre-condicao: tabela empresas legada SEM os 5 campos")

from app.services.migrations import ensure_schema
ensure_schema(eng)  # deve adicionar as 5 colunas
ensure_schema(eng)  # idempotente: rodar 2x nao quebra

cols_depois = {c["name"] for c in inspect(eng).get_columns("empresas")}
for c in novos:
    check(c in cols_depois, f"ensure_schema adicionou empresas.{c}")
eng.dispose()


# =========================================================================
# PARTE 2: app via TestClient (startup roda create_all + ensure_schema + seed)
# =========================================================================
# Limpa modulos para reimportar config/database com o DATABASE_URL novo
for m in list(sys.modules):
    if m.startswith("app."):
        del sys.modules[m]

from fastapi.testclient import TestClient
import app.main as main_mod
importlib.reload(main_mod)

with TestClient(main_mod.app) as client:
    # startup nao quebrou (login dos seeds funciona)
    r = client.get("/health")
    check(r.status_code == 200, "startup/health 200")

    # login dos usuarios seed (marcos/joao/admin)
    def login(email, senha):
        rr = client.post("/auth/login", json={"email": email, "senha": senha})
        return rr

    rm = login("marcos@frigorifico.com", "senha123")
    rj = login("joao@boidourado.com", "senha123")
    ra = login("admin@proteinaja.com", "admin123")
    check(rm.status_code == 200, "login marcos 200 (startup/seed ok)")
    check(rj.status_code == 200, "login joao 200")
    check(ra.status_code == 200, "login admin 200")
    tok_marcos = rm.json().get("access_token")
    tok_joao = rj.json().get("access_token")
    tok_admin = ra.json().get("access_token")

    def H(t):
        return {"Authorization": f"Bearer {t}"}

    # ---- REGISTER: cria empresa + usuario ----
    reg = client.post("/auth/register", json={
        "nome": "Bob", "email": "bob@novaempresa.com", "senha": "secret123",
        "nome_empresa": "Acougue do Bob"
    })
    check(reg.status_code == 200, f"register 200 (got {reg.status_code})")
    tok_bob = reg.json().get("access_token")
    check(bool(tok_bob), "register retorna access_token")

    # novo usuario ve a PROPRIA empresa em /company
    comp_bob = client.get("/company", headers=H(tok_bob))
    check(comp_bob.status_code == 200, "GET /company do bob 200")
    cb = comp_bob.json()
    check(cb.get("nome") == "Acougue do Bob", "empresa do bob = nome_empresa enviado")
    check(cb.get("plano") == "starter", "empresa do bob plano=starter")
    check(cb.get("ativo") is True, "empresa do bob ativo=True")
    bob_empresa_id = cb.get("id")

    # /auth/me confirma role=empresa e empresa_id setado
    me_bob = client.get("/auth/me", headers=H(tok_bob)).json()
    check(me_bob.get("role") == "empresa", "bob role=empresa")
    check(me_bob.get("empresa_id") == bob_empresa_id, "bob empresa_id == empresa criada")

    # ISOLAMENTO: empresa do bob != empresa do marcos
    comp_marcos = client.get("/company", headers=H(tok_marcos)).json()
    check(comp_marcos.get("id") != bob_empresa_id, "isolamento: empresa marcos != empresa bob")

    # register default de nome quando nome_empresa ausente
    reg2 = client.post("/auth/register", json={
        "nome": "Alice", "email": "alice@x.com", "senha": "secret123"
    })
    check(reg2.status_code == 200, "register sem nome_empresa 200")
    comp_alice = client.get("/company", headers=H(reg2.json()["access_token"])).json()
    check(comp_alice.get("nome") == "Empresa de Alice", "default nome = 'Empresa de Alice'")

    # 409 email duplicado
    dup = client.post("/auth/register", json={
        "nome": "Bob2", "email": "bob@novaempresa.com", "senha": "x123456"
    })
    check(dup.status_code == 409, f"register email duplicado 409 (got {dup.status_code})")

    # ---- PATCH /company: 5 campos novos ----
    patch = client.patch("/company", headers=H(tok_bob), json={
        "email_contato": "contato@bob.com",
        "telefone": "62999990000",
        "endereco": "Rua 1, 100",
        "responsavel": "Bob Silva",
        "segmento": "Bovino",
    })
    check(patch.status_code == 200, f"PATCH /company 200 (got {patch.status_code})")
    pj = patch.json()
    check(pj.get("email_contato") == "contato@bob.com", "PATCH persiste email_contato")
    check(pj.get("telefone") == "62999990000", "PATCH persiste telefone")
    check(pj.get("endereco") == "Rua 1, 100", "PATCH persiste endereco")
    check(pj.get("responsavel") == "Bob Silva", "PATCH persiste responsavel")
    check(pj.get("segmento") == "Bovino", "PATCH persiste segmento")
    # persistencia real (GET de novo)
    comp_bob2 = client.get("/company", headers=H(tok_bob)).json()
    check(comp_bob2.get("segmento") == "Bovino", "PATCH persistido apos novo GET")

    # ---- /dashboard/analytics: estrutura + isolamento ----
    am = client.get("/dashboard/analytics", headers=H(tok_marcos))
    aj = client.get("/dashboard/analytics", headers=H(tok_joao))
    aa = client.get("/dashboard/analytics", headers=H(tok_admin))
    check(am.status_code == 200, "analytics marcos 200")
    check(aj.status_code == 200, "analytics joao 200")
    check(aa.status_code == 200, "analytics admin 200")
    dm, dj, da = am.json(), aj.json(), aa.json()

    # 14 dias, incluindo zeros
    check(len(dm["faturamento_por_dia"]) == 14, "faturamento_por_dia tem 14 dias")
    dias = [d["dia"] for d in dm["faturamento_por_dia"]]
    check(dias == sorted(dias), "faturamento_por_dia ordenado por data asc")
    hoje = datetime.utcnow().date()
    esperados = [(hoje - timedelta(days=i)).isoformat() for i in range(13, -1, -1)]
    check(dias == esperados, "faturamento_por_dia cobre exatamente ultimos 14 dias UTC")

    # pedidos_por_status com as 4 chaves
    for k in ("confirmado", "negociando", "aguardando", "entregue"):
        check(k in dm["pedidos_por_status"], f"pedidos_por_status tem chave {k}")

    # ISOLAMENTO real: marcos != joao em algum agregado
    fat_m = sum(d["total"] for d in dm["faturamento_por_dia"])
    fat_j = sum(d["total"] for d in dj["faturamento_por_dia"])
    check(dm["top_clientes"] != dj["top_clientes"] or fat_m != fat_j,
          "isolamento: analytics marcos != joao")

    # admin agregado >= soma das empresas (admin ve tudo)
    fat_a = sum(d["total"] for d in da["faturamento_por_dia"])
    check(fat_a >= fat_m and fat_a >= fat_j, "admin agregado >= cada empresa")
    check(fat_a + 0.01 >= fat_m + fat_j - 0.01, "admin agregado ~= soma das empresas (>=)")

    # top_produtos parseou itens_json (receita/qtd > 0 para quem tem pedidos)
    if dm["top_produtos"]:
        tp = dm["top_produtos"][0]
        check(tp["receita"] > 0 and tp["qtd_kg"] > 0, "top_produtos: receita e qtd_kg > 0")
        # ordenado por receita desc
        receitas = [p["receita"] for p in dm["top_produtos"]]
        check(receitas == sorted(receitas, reverse=True), "top_produtos ordenado por receita desc")
    else:
        check(True, "top_produtos vazio (sem pedidos com itens) - tolerado")

    # ticket_medio / total_a_receber / total_pago presentes e numericos
    for k in ("ticket_medio", "total_a_receber", "total_pago"):
        check(isinstance(dm[k], (int, float)), f"analytics tem {k} numerico")

    # ---- parse defensivo de itens_json ruim: injeta pedido com JSON invalido ----
    from app.database import SessionLocal
    from app.models import Pedido, Cliente, Conversa, PedidoOrigem, PedidoStatus
    db = SessionLocal()
    try:
        cli = db.query(Cliente).filter(Cliente.empresa_id == comp_marcos["id"]).first()
        if cli is None:
            cli = db.query(Cliente).first()
        conv = db.query(Conversa).first()
        if cli and conv:
            db.add(Pedido(
                conversa_id=conv.id, cliente_id=cli.id, empresa_id=comp_marcos["id"],
                itens_json="{nao eh json valido", valor_total=10.0,
                origem=PedidoOrigem.humano, status=PedidoStatus.aguardando, pago=False,
            ))
            # tambem um itens_json que e um dict (nao lista) e um item sem 'produto'
            db.add(Pedido(
                conversa_id=conv.id, cliente_id=cli.id, empresa_id=comp_marcos["id"],
                itens_json=json.dumps({"foo": "bar"}), valor_total=5.0,
                origem=PedidoOrigem.humano, status=PedidoStatus.aguardando, pago=False,
            ))
            db.add(Pedido(
                conversa_id=conv.id, cliente_id=cli.id, empresa_id=comp_marcos["id"],
                itens_json=json.dumps([{"qtd_kg": 2, "preco_kg": 3}]), valor_total=6.0,
                origem=PedidoOrigem.humano, status=PedidoStatus.aguardando, pago=False,
            ))
            db.commit()
            ok_inject = True
        else:
            ok_inject = False
    finally:
        db.close()

    am2 = client.get("/dashboard/analytics", headers=H(tok_marcos))
    check(am2.status_code == 200, "analytics nao quebra com itens_json invalido/dict/sem-produto")

print(f"\n=== {checks - len(failures)}/{checks} asserts OK ===")
if failures:
    print("FALHAS:")
    for f in failures:
        print(" -", f)
    sys.exit(1)
print("TODOS OS ASSERTS PASSARAM")
sys.exit(0)
