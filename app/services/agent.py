import json

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


def extrair_pedido(historico: list[Mensagem], mensagem_cliente: str, produtos=None) -> list[dict]:
    """Extrai um pedido FECHADO a partir da conversa, usando o Groq.

    Retorna uma lista de itens [{"produto", "qtd_kg"}] APENAS quando o cliente
    CONFIRMOU um pedido com quantidades definidas. Caso contrario (sem pedido
    fechado, em duvida, ou em qualquer falha), retorna [].

    Os nomes de 'produto' sao casados com a lista 'produtos' (nomes do catalogo)
    fornecida. Parse totalmente defensivo: qualquer excecao -> [].
    """
    try:
        nomes_catalogo = []
        if produtos:
            for p in produtos:
                # produtos pode ser lista de (nome, preco) ou de strings.
                if isinstance(p, (tuple, list)):
                    nomes_catalogo.append(str(p[0]))
                else:
                    nomes_catalogo.append(str(p))
        catalogo_txt = ", ".join(nomes_catalogo) if nomes_catalogo else "(catálogo não informado)"

        system_prompt = (
            "Você é um extrator de pedidos. Analise a conversa de WhatsApp entre um "
            "frigorífico e um cliente B2B e determine se há um PEDIDO FECHADO, ou seja, "
            "se o cliente CONFIRMOU itens com quantidades definidas (em kg).\n\n"
            f"Produtos válidos do catálogo: {catalogo_txt}\n\n"
            "Regras:\n"
            "- Responda SOMENTE com JSON válido, sem texto extra, no formato "
            '{\"itens\":[{\"produto\":\"<nome do catálogo>\",\"qtd_kg\":<número>}]}.\n'
            "- Use EXATAMENTE os nomes do catálogo acima para o campo \"produto\".\n"
            "- Inclua itens apenas quando o cliente confirmou o pedido com quantidades claras.\n"
            "- Se NÃO houver pedido fechado, se estiver em negociação, ou em caso de "
            'qualquer dúvida, responda {\"itens\":[]}.'
        )

        historico_formatado = montar_historico(historico)
        messages = (
            [{"role": "system", "content": system_prompt}]
            + historico_formatado
            + [{"role": "user", "content": mensagem_cliente}]
        )

        response = client_groq.chat.completions.create(
            model="llama-3.1-8b-instant",
            max_tokens=500,
            messages=messages,
        )
        conteudo = response.choices[0].message.content or ""

        # Extrai o bloco JSON de forma defensiva (modelo pode incluir cercas/texto).
        inicio = conteudo.find("{")
        fim = conteudo.rfind("}")
        if inicio == -1 or fim == -1 or fim < inicio:
            return []
        dados = json.loads(conteudo[inicio : fim + 1])

        itens_raw = dados.get("itens", [])
        if not isinstance(itens_raw, list):
            return []

        resultado: list[dict] = []
        for item in itens_raw:
            if not isinstance(item, dict):
                continue
            produto = item.get("produto")
            qtd = item.get("qtd_kg")
            if not produto:
                continue
            try:
                qtd_f = float(qtd)
            except (TypeError, ValueError):
                continue
            if qtd_f <= 0:
                continue
            resultado.append({"produto": str(produto), "qtd_kg": qtd_f})
        return resultado
    except Exception:
        return []
