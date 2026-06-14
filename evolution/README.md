# Evolution API (WhatsApp) — guia de deploy

**Plataforma recomendada:** Koyeb (compute always-on, free) + Neon (Postgres free, persistente) + cache local (Redis desligado)

**Gratuito:** sim  |  **Precisa criar conta:** sim

## Resumo

Para manter a Evolution API rodando 24/7 com a sessao do WhatsApp viva, o requisito decisivo e "nao dormir por inatividade". Isso elimina o free tier do Render (web service dorme em 15 min, com cold start de ~1 min, derrubando a conexao do WhatsApp), do Railway (so da ~$1/mes de credito, pausa quando acaba) e do Fly.io (perdeu o free tier para contas novas em 2026, exige cartao). 

A unica plataforma com free tier que roda um container Docker SEMPRE LIGADO (sem scale-to-zero, sem sleep) em 2026 e a Koyeb: 1 web service free com 512MB RAM / 0.1 vCPU / 2GB SSD, always-on. Coincide exatamente com o minimo de RAM da Evolution API (512MB), entao da para uma demo academica com 1 instancia de WhatsApp.

O problema: a Evolution API v2 EXIGE Postgres (nao roda sem banco; suporte a SQLite e bugado). E o Postgres free da propria Koyeb so da 5h de tempo ativo por mes (inutil para algo persistente), e o do Render free EXPIRA em 30 dias. Por isso o banco vai para fora, no Neon: free tier sem data de expiracao, 0.5GB, e mesmo com scale-to-zero ele acorda em <500ms na primeira query (a Evolution reconecta sozinha). O Redis e desligado e usamos CACHE_LOCAL_ENABLED=true, evitando um terceiro servico.

Resultado: Koyeb (Evolution API, always-on) + Neon (Postgres persistente) + cache local. Tudo gratuito. Unica friccao: a Koyeb pede cartao de credito no cadastro (anti-fraude), mas nao cobra nada pelo instance free.

Alternativa se quiser ZERO cartao de credito: rodar localmente via docker-compose so na hora de apresentar (incluido nos arquivos). E o caminho mais simples e 100% gratis para uma demo academica, mas so fica no ar enquanto seu PC estiver ligado.


## Passos (voce precisa fazer manualmente)

1. 1. Criar conta no Neon (neon.tech) com login pelo GitHub. Criar um projeto/banco chamado 'evolution' na regiao mais proxima (AWS sa-east-1 Sao Paulo, se disponivel). Copiar a connection string (formato postgresql://user:senha@host/dbname?sslmode=require).
2. 2. Criar conta na Koyeb (koyeb.com) com login pelo GitHub. Vai precisar cadastrar um cartao de credito (eles nao cobram pelo instance free, e so anti-fraude).
3. 3. No painel da Koyeb: Create Service > Docker > usar a imagem 'atendai/evolution-api:v2.1.1'. Definir a porta de exposicao como 8080 (Public, HTTP, path /). Escolher o Instance type 'Free' (Eco/Free 512MB).
4. 4. Na aba Environment variables da Koyeb, colar as variaveis do arquivo .env.example (ver abaixo): trocar AUTHENTICATION_API_KEY por uma chave forte sua, e colar a connection string do Neon em DATABASE_CONNECTION_URI. Marcar AUTHENTICATION_API_KEY e DATABASE_CONNECTION_URI como 'Secret'.
5. 5. (Opcional, em vez do painel) Instalar o Koyeb CLI e rodar 'koyeb deploy' usando o koyeb.yaml fornecido, depois de setar os secrets com 'koyeb secret create evolution-api-key' e 'koyeb secret create neon-db-uri'.
6. 6. Fazer o deploy e esperar ficar 'Healthy'. A Koyeb vai te dar uma URL publica tipo https://<nome>-<org>.koyeb.app
7. 7. Testar a API: abrir https://SEU-APP.koyeb.app/manager no navegador (o Manager da Evolution v2) e logar com a AUTHENTICATION_API_KEY. Ou chamar GET https://SEU-APP.koyeb.app/ com header 'apikey: SUA_CHAVE'.
8. 8. Criar uma instancia de WhatsApp pelo Manager (ou via POST /instance/create com body {"instanceName":"proteinaja","integration":"WHATSAPP-BAILEYS"}).
9. 9. Escanear o QR code que aparece no Manager com o WhatsApp do celular (Aparelhos conectados > Conectar um aparelho). A conexao fica viva porque a Koyeb nao dorme.
10. 10. Apontar o backend FastAPI (no Render) para a nova URL: setar a env var da Evolution (ex EVOLUTION_API_URL=https://SEU-APP.koyeb.app e EVOLUTION_API_KEY=sua chave) no painel do Render.
11. 11. Remover/desabilitar os workflows obsoletos de deploy SSH para Oracle (deploy.yml / setup.yml) nos repos para nao falharem no GitHub Actions.

## Observacoes

LIMITACOES HONESTAS:

1. RAM apertada. O instance free da Koyeb tem exatamente 512MB, que e o MINIMO da Evolution API. Funciona para 1 instancia de WhatsApp numa demo academica, mas pode ficar lento ou ate reiniciar (OOM) se houver muitos contatos/mensagens. Nao serve para producao seria.

2. Koyeb pede cartao de credito no cadastro (anti-fraude). Nao cobra pelo instance free, mas se voce nao quiser dar cartao de jeito nenhum, use o docker-compose local (fallback) na hora de apresentar.

3. Limite de 1 service free por organizacao na Koyeb. Como o backend FastAPI ja esta no Render e o frontend no Vercel, isso esta ok - a Koyeb fica so para a Evolution API.

4. Banco no Neon faz scale-to-zero. Apos alguns minutos sem query o compute do Neon hiberna; a primeira chamada acorda em <500ms. Para a Evolution isso e transparente (ela reconecta), mas a primeiríssima requisicao apos ociosidade pode ter um pequeno atraso. O dado NAO e perdido e o projeto NAO expira (diferente do Render free, que apaga o Postgres em 30 dias).

5. Por que NAO Render para a Evolution: o web service free do Render dorme apos 15 min de inatividade e leva ~1 min para acordar. Toda vez que dorme, a conexao do WhatsApp (websocket Baileys) cai e precisa reconectar/reescanear QR. Isso inviabiliza o uso persistente que voce pediu. Por isso a compute foi para a Koyeb (always-on) e nao para o Render.

6. Redis desligado. Usei CACHE_LOCAL_ENABLED=true para nao precisar de um terceiro servico (nenhum free tier bom de Redis always-on sobrou em 2026). Para 1 instancia de demo, o cache local resolve. Se um dia precisar escalar, ai sim adicionar Upstash/Redis.

7. A imagem oficial atual e atendai/evolution-api:v2.1.1. Existe tambem o fork evoapicloud/evolution-api; se a atendai parar de receber updates, troque o nome da imagem nos arquivos. Evite ':latest' em producao para nao quebrar com mudanca de schema.

8. Os workflows GitHub Actions antigos (deploy.yml/setup.yml com appleboy/ssh-action para a Oracle) devem ser removidos ou desabilitados, senao vao falhar a cada push. Voce pediu para eu NAO rodar git, entao isso fica como passo manual.

9. Os repos locais nao foram encontrados nos caminhos informados (a pasta proteinaja-backend e a pasta do projeto apareceram vazias para mim nesta sessao). Os arquivos acima estao prontos para voce colar na raiz do repo do backend (ou onde mantiver a infra da Evolution).

## Arquivos nesta pasta

- `koyeb.yaml` — config de deploy na Koyeb (always-on, free)
- `.env.example` — variaveis de ambiente da Evolution API
- `docker-compose.evolution.yml` — alternativa: rodar localmente (demo, sem cartao)