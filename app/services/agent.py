from groq import Groq
from app.config import settings
from app.models import Mensagem, Cliente

client_groq = Groq(api_key=settings.groq_api_key)

CATALOGO = """
Produtos disponíveis:
- Picanha bovina: R$ 89/kg (mínimo 5kg)
- Fraldinha bovina: R$ 52/kg (mínimo 5kg)
- Alcatra bovina: R$ 58/kg (mínimo 5kg)
- Contra-filé: R$ 55/kg (mínimo 5kg)
- Acém bovino: R$ 34/kg (mínimo 10kg)
- Músculo bovino: R$ 32/kg (mínimo 10kg)
- Peito de frango: R$ 14/kg (mínimo 10kg)
- Frango inteiro: R$ 13/kg (mínimo 10kg)
- Costela bovina: R$ 38/kg (mínimo 5kg)
- Linguiça suína: R$ 18/kg (mínimo 5kg)
Prazo de entrega padrão: 2 dias úteis após confirmação.
Formas de pagamento: boleto (30 dias) ou PIX (à vista com 2% desconto).
"""

def montar_historico(mensagens: list[Mensagem]) -> list[dict]:
    historico = []
    for msg in mensagens[-20:]:
        if msg.origem == "cliente":
            historico.append({"role": "user", "content": msg.texto})
        elif msg.origem in ("agente", "humano"):
            historico.append({"role": "assistant", "content": msg.texto})
    return historico

def gerar_resposta(mensagem_cliente: str, historico: list[Mensagem], cliente: Cliente, produtos=None) -> str:
    tipo_label = {
        "acougue": "açougue", "restaurante": "restaurante",
        "mercadinho": "mercadinho", "food_service": "food service",
    }.get(cliente.tipo.value, "estabelecimento")

    if produtos:
        tabela = "; ".join(f"{nome} {float(preco):.2f}" for nome, preco in produtos)
        catalogo = f"Tabela de preços atual (R$/kg): {tabela}.\nPrazo de entrega padrão: 2 dias úteis após confirmação.\nFormas de pagamento: boleto (30 dias) ou PIX (à vista com 2% desconto)."
    else:
        catalogo = CATALOGO

    system_prompt = f"""Você é o assistente comercial do {settings.frigorifico_nome}, frigorífico localizado em {settings.frigorifico_cidade}.

Você atende via WhatsApp compradores B2B — açougues, restaurantes e mercadinhos. Seu trabalho é receber pedidos, confirmar itens, calcular valores e fechar o pedido.

Cliente atual: {cliente.nome} ({tipo_label}, {cliente.cidade or 'localização não informada'})

{catalogo}

Regras:
- Responda sempre em português informal e direto, como um atendente humano faria no WhatsApp
- Se o cliente pedir algo fora do catálogo, informe que não trabalhamos com esse produto
- Ao confirmar um pedido, liste os itens, quantidades, valor total e prazo de entrega
- Se o cliente pedir desconto maior que 5%, diga que precisa verificar com o gerente (isso escalará para humano)
- Nunca invente preços ou produtos que não estão no catálogo
- Mensagens curtas e diretas — sem parágrafos longos"""

    historico_formatado = montar_historico(historico)
    messages = [{"role": "system", "content": system_prompt}] + historico_formatado + [{"role": "user", "content": mensagem_cliente}]

    response = client_groq.chat.completions.create(
        model="llama-3.1-8b-instant",
        max_tokens=500,
        messages=messages,
    )
    return response.choices[0].message.content

def deve_escalar_para_humano(resposta: str) -> bool:
    gatilhos = ["verificar com o gerente", "falar com o responsável", "vou checar com a equipe"]
    return any(g in resposta.lower() for g in gatilhos)
