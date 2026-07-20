# Orkestral

Plataforma SaaS multiempresa de automação empresarial, integrações, agentes de inteligência artificial e módulos operacionais.

O repositório contém a fundação executável, identidade multiempresa, autorização granular, núcleo modular, CRM, agentes, conhecimento, automações, integrações, relatórios, auditoria, planos, notificações e módulos operacionais.

## Manual da plataforma

O [Guia completo de uso da Orkestral](docs/GUIA_COMPLETO_DE_USO.md) explica a plataforma em linguagem simples, com imagens reais, endereços de cada tela, cuidados de segurança e exemplos práticos de automações e integrações.

A avaliação das atualizações automáticas está registrada na [Revisão de dependências de 20/07/2026](docs/maintenance/dependency-review-2026-07-20.md).

## Pré-requisitos

- Docker Desktop com containers Linux e Docker Compose v2;
- opcionalmente, Node.js 24 + pnpm 11 e Python 3.13 + uv 0.11 para desenvolvimento fora de containers.

## Início rápido

Na raiz do repositório:

Antes de iniciar, verifique automaticamente todas as ferramentas, versões, dependências e portas:

```powershell
.\check-environment.ps1
```

No macOS/Linux, pressione `F5` no VS Code ou execute `scripts/dev.sh start` depois de instalar e iniciar o Docker.

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

## Acesso de desenvolvimento

A inicialização local cria, de forma idempotente, uma empresa e um administrador somente quando `BOOTSTRAP_ENABLED=true`:

```text
E-mail: admin@orkestral.dev.br
Senha:  Orkestral-Dev-2026!
```

Entre em `http://localhost/login`. Essas credenciais pertencem exclusivamente ao `.env.example`, são rejeitadas em produção e devem ser substituídas fora do ambiente local.

O administrador pode cadastrar empresas em `/app/empresas`, configurar papéis em `/app/papeis`, convidar membros em `/app/usuarios` e ativar o CRM em `/app/modulos`. Depois da ativação, os contatos ficam disponíveis em `/app/crm/contatos`. Sem provedor de e-mail nesta etapa, links de convite e redefinição aparecem na própria interface apenas quando `DEVELOPMENT_EXPOSE_TOKENS=true`.

## Prévia do shell

Com `VITE_AUTH_PREVIEW_ENABLED=true` e o servidor Vite em modo development, o shell autenticado pode ser visto em:

```text
http://localhost:5173/preview/app
```

O build de produção falha se essa flag estiver ativa. A prévia não cria usuário nem sessão; `/app` exige autenticação real.

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

Não versionar `.env`, certificados, tokens ou dumps. Access tokens permanecem somente em memória; refresh tokens opacos ficam em cookies HttpOnly, são rotacionados a cada renovação e podem ser revogados no servidor.

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

Consulte o [guia completo de uso](docs/GUIA_COMPLETO_DE_USO.md), [a visão de arquitetura](docs/architecture/overview.md), [a API de autenticação](docs/api/authentication.md), [a API de autorização](docs/api/authorization.md), [o núcleo modular](docs/architecture/modularity.md), [a API do CRM](docs/api/crm.md) e o [guia de solução de problemas](docs/troubleshooting.md).
