from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import Base, engine
from app.routers import auth, webhook, dashboard, clients, orders, conversations

app = FastAPI(title="ProteínaJá API", version="1.0.0")

@app.on_event("startup")
def create_tables():
    Base.metadata.create_all(bind=engine)

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

@app.get("/health")
def health():
    return {"status": "ok"}
