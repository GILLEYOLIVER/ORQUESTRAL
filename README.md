# Orkestral

Fundação da plataforma SaaS multiempresa de automação empresarial e agentes de inteligência artificial.

Esta entrega cobre a **Fase 1**: monorepo, API, web, worker, infraestrutura local, contratos, testes e CI. Empresas, usuários, autenticação real e módulos de negócio começam na Fase 2.

## Pré-requisitos

- Docker Desktop com containers Linux e Docker Compose v2;
- opcionalmente, Node.js 24 + pnpm 11 e Python 3.13 + uv 0.11 para desenvolvimento fora de containers.

## Início rápido

Na raiz do repositório:

Antes de iniciar, verifique automaticamente todas as ferramentas, versões, dependências e portas:

```powershell
.\check-environment.ps1
```

Para obter saída estruturada:

```powershell
.\check-environment.ps1 -Json
```

O script retorna código `0` quando o ambiente está completo e `1` quando existem requisitos pendentes.

Em seguida, inicie os serviços:

```bash
docker compose --env-file .env.example -f docker-compose.yml -f docker-compose.development.yml up --build
```

Depois da inicialização:

| Serviço            | Endereço local          |
| ------------------ | ----------------------- |
| Orkestral          | http://localhost        |
| Web Vite           | http://localhost:5173   |
| API                | http://localhost:8000   |
| Health             | http://localhost/health |
| Readiness          | http://localhost/ready  |
| n8n técnico        | http://localhost:5678   |
| Console de objetos | http://localhost:9001   |

O n8n e os consoles auxiliares são publicados apenas no override de desenvolvimento e somente em `127.0.0.1`.

Para encerrar:

```bash
docker compose --env-file .env.example -f docker-compose.yml -f docker-compose.development.yml down
```

Use `down -v` somente quando quiser apagar deliberadamente todos os dados locais.

## Prévia autenticada

A autenticação não é simulada. O formulário de login valida os campos e informa que o acesso real será implementado na Fase 2.

Com `VITE_AUTH_PREVIEW_ENABLED=true` e o servidor Vite em modo development, o shell autenticado pode ser visto em:

```text
http://localhost:5173/preview/app
```

O build de produção falha se essa flag estiver ativa. A rota `/app` permanece protegida e redireciona usuários anônimos.

## Desenvolvimento sem Docker

```bash
uv sync --all-packages --all-extras
pnpm install --frozen-lockfile
uv run pytest -m "not integration"
uv run ruff check apps tests
uv run mypy apps/api apps/worker
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```

Para iniciar os serviços diretamente, configure PostgreSQL e Redis e execute:

```bash
cd apps/api
uv run alembic -c alembic.ini upgrade head
uv run uvicorn app.main:app --reload
```

Em outro terminal:

```bash
uv run celery -A worker.main:celery_app worker --loglevel=INFO
pnpm dev:web
```

## Contratos

O OpenAPI da API é exportado para `openapi.json` e convertido em tipos TypeScript:

```bash
pnpm contracts:generate
```

O CI repete a geração e falha se os arquivos versionados estiverem desatualizados.

## Configuração e segurança

`.env.example` contém somente valores conhecidos de desenvolvimento. Copie e substitua os valores em qualquer outro ambiente. Quando `APP_ENV=production`, a API rejeita placeholders, segredos menores que 32 caracteres e valores marcados como desenvolvimento.

Não versionar `.env`, certificados, tokens ou dumps. Access tokens futuros permanecerão em memória e refresh tokens serão cookies HttpOnly.

## Estrutura

```text
apps/api       FastAPI, SQLAlchemy, Alembic e testes
apps/web       React, Vite, rotas e interface
apps/worker    Celery e tarefas assíncronas
packages       tipos compartilhados, design system e espaço do SDK
infrastructure Docker, Nginx e monitoramento
docs           arquitetura, APIs, banco, plugins e decisões
tests          integração, segurança e ponta a ponta
```

Consulte [a visão de arquitetura](docs/architecture/overview.md) e o [guia de solução de problemas](docs/troubleshooting.md).
