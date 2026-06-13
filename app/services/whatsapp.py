import httpx
from app.config import settings

BASE = settings.evolution_api_url
HEADERS = {"apikey": settings.evolution_api_key, "Content-Type": "application/json"}
INSTANCE = settings.evolution_instance_name

async def enviar_mensagem(numero: str, texto: str) -> bool:
    url = f"{BASE}/message/sendText/{INSTANCE}"
    payload = {"number": numero, "text": texto}
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.post(url, json=payload, headers=HEADERS)
        return r.status_code == 201

async def criar_instancia() -> dict:
    url = f"{BASE}/instance/create"
    payload = {"instanceName": INSTANCE, "qrcode": True}
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.post(url, json=payload, headers=HEADERS)
        return r.json()

async def obter_qrcode() -> str | None:
    url = f"{BASE}/instance/connect/{INSTANCE}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(url, headers=HEADERS)
        data = r.json()
        return data.get("base64")
