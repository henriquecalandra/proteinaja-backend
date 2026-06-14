from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import Base, engine
from app.routers import auth, webhook, dashboard, clients, orders, conversations, products, admin, company

app = FastAPI(title="ProteínaJá API", version="1.0.0")

@app.on_event("startup")
def create_tables():
    from app.database import SessionLocal
    from app.models import Usuario
    from app.services.auth import hash_senha
    Base.metadata.create_all(bind=engine)
    # Migracao leve: garante colunas adicionadas apos a criacao inicial do banco
    # (create_all nao altera tabelas existentes no Postgres do Render).
    from app.services.migrations import ensure_schema
    ensure_schema(engine)
    db = SessionLocal()
    try:
        if not db.query(Usuario).filter(Usuario.email == "marcos@frigorifico.com").first():
            db.add(Usuario(nome="Marcos Ribeiro", email="marcos@frigorifico.com", senha_hash=hash_senha("senha123")))
            db.commit()
        # Seed de dados de demonstracao (idempotente e defensivo).
        # NUNCA pode derrubar o startup: a propria seed_demo trata excecoes,
        # mas envolvemos em try/except por seguranca extra.
        try:
            from app.services.seed_demo import seed_demo
            seed_demo(db)
        except Exception:
            import logging
            logging.getLogger("startup").exception("Falha ao rodar seed_demo (ignorado)")
    finally:
        db.close()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(webhook.router)
app.include_router(dashboard.router)
app.include_router(clients.router)
app.include_router(orders.router)
app.include_router(conversations.router)
app.include_router(products.router)
app.include_router(admin.router)
app.include_router(company.router)

@app.get("/health")
def health():
    return {"status": "ok"}
