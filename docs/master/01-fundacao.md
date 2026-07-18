# DOCUMENTO MESTRE DE DESENVOLVIMENTO — ORKESTRAL

**Versão da especificação:** 1.1  
**Atualização:** inclui o fluxo oficial de desenvolvimento pelo VS Code com inicialização por `F5` e acesso administrativo estritamente local.

## 1. IDENTIFICAÇÃO DO PROJETO

**Nome do sistema:** Orkestral  
**Tipo de sistema:** Plataforma SaaS multiempresa de automação empresarial e agentes de Inteligência Artificial.

A Orkestral será uma plataforma central para empresas automatizarem processos, conectarem sistemas, utilizarem agentes de IA e administrarem integrações por meio de uma interface simples.

O sistema deverá atender empresas de diferentes segmentos sem exigir alterações no núcleo do código. Cada cliente poderá ativar apenas os módulos, agentes, plugins e automações de que precisar.

Exemplos de segmentos atendidos:

* Indústrias;
* Escritórios;
* Clínicas;
* Imobiliárias;
* Lojas;
* Prestadores de serviços;
* Confecções;
* Restaurantes;
* Escolas;
* Transportadoras;
* Empresas de tecnologia;
* Empresas de contabilidade.

A plataforma deverá ser modular, extensível, segura, multiempresa e preparada para crescer.

---

# 2. OBJETIVO PRINCIPAL

Desenvolva uma plataforma capaz de:

1. Cadastrar várias empresas.
2. Manter os dados de cada empresa isolados.
3. Cadastrar usuários e permissões.
4. Ativar módulos separadamente para cada empresa.
5. Cadastrar e configurar agentes de IA.
6. Conectar agentes a ferramentas e plugins.
7. Criar automações empresariais.
8. Executar fluxos no n8n sem expor o painel do n8n ao cliente.
9. Integrar WhatsApp, e-mail, calendários, ERPs, CRMs e outras APIs.
10. Controlar consumo de tokens, execuções e custos.
11. Manter histórico, logs e auditoria.
12. Oferecer dashboards e relatórios.
13. Permitir expansão sem alterações destrutivas no núcleo.

---

# 3. TECNOLOGIAS PRINCIPAIS

## Front-end

* React;
* TypeScript;
* Vite;
* React Router;
* TanStack Query;
* biblioteca de formulários com validação;
* cliente HTTP centralizado;
* sistema de componentes reutilizáveis.

## Back-end

* Python;
* FastAPI;
* SQLAlchemy assíncrono;
* Alembic para migrações;
* Pydantic para validação;
* PostgreSQL;
* Redis;
* sistema de filas para trabalhos assíncronos;
* integração interna com n8n.

## Infraestrutura

* Docker;
* Docker Compose;
* Nginx;
* HTTPS;
* GitHub Actions;
* armazenamento compatível com S3 para documentos;
* monitoramento e logs estruturados.

Não prenda o núcleo a um único fornecedor de IA, armazenamento, mensageria ou integração.

---

# 4. REGRA FUNDAMENTAL DE MULTIEMPRESA

Todo registro pertencente a um cliente deverá possuir uma referência para a empresa responsável.

Use o conceito de `tenant`, representado inicialmente pela entidade `Company`.

A maioria das tabelas de negócio deverá possuir:

```text
company_id
```

Nunca aceite o `company_id` enviado livremente pelo front-end como fonte confiável.

O back-end deverá obter a empresa atual pelo usuário autenticado e pelo contexto da requisição.

Toda consulta deverá ser filtrada pela empresa atual.

Exemplo conceitual:

```python
contact = await repository.get_by_id(
    contact_id=contact_id,
    company_id=current_context.company_id,
)
```

Nunca faça:

```python
contact = await repository.get_by_id(contact_id=contact_id)
```

A segunda forma pode causar vazamento de dados entre empresas.

Crie testes automáticos que comprovem que um usuário de uma empresa não consegue visualizar ou alterar registros de outra.

---

# 5. ESTRUTURA INICIAL DO REPOSITÓRIO

Crie um monorepositório com esta estrutura:

```text
orkestral/
├── apps/
│   ├── api/
│   ├── web/
│   └── worker/
├── packages/
│   ├── shared-types/
│   ├── ui-components/
│   └── plugin-sdk/
├── infrastructure/
│   ├── docker/
│   ├── nginx/
│   ├── monitoring/
│   └── scripts/
├── docs/
├── tests/
├── docker-compose.yml
├── docker-compose.development.yml
├── .env.example
├── .gitignore
├── README.md
└── Makefile
```

Dentro do back-end, mantenha `main.py`, `core/`, `modules/`, `shared/` e `migrations/`. Cada módulo deve separar domínio, modelos, schemas, repositórios, serviços, rotas, permissões e testes quando aplicável. Não concentre a aplicação em arquivos gigantes.

---

# 6. FASE 1 — FUNDAÇÃO DO PROJETO

## Objetivo

Criar uma base executável, organizada e documentada.

## 6.1 Back-end

Crie a aplicação FastAPI em `apps/api/app/main.py` com inicialização, configurações, PostgreSQL, Redis, tratamento de erros, identificação de requisição, logs estruturados e as rotas:

```text
GET /health
GET /ready
```

`/ready` deve verificar PostgreSQL, Redis e configurações obrigatórias.

## 6.2 Configuração central

Crie `apps/api/app/core/config.py` e leia as configurações por variáveis de ambiente, incluindo `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`, `ENCRYPTION_KEY`, `N8N_BASE_URL`, `N8N_API_KEY` e credenciais de armazenamento. Mantenha `.env.example` sem segredos reais.

## 6.3 Front-end

Crie React com TypeScript em `apps/web/`, incluindo rotas, layouts público e autenticado, login, página inicial, página de erro, cliente HTTP, sessão e tratamento global de erros.

## 6.4 Docker Compose

Configure `api`, `web`, `worker`, `postgres`, `redis`, `n8n`, `object-storage` e `nginx`. Em produção, o n8n deverá estar disponível apenas na rede interna.

## 6.5 Migrações

Configure Alembic e crie as extensões e estruturas iniciais necessárias.

## 6.6 Experiência de desenvolvimento com VS Code e F5

Crie uma configuração compartilhada de desenvolvimento:

```text
.vscode/launch.json
.vscode/tasks.json
scripts/dev.ps1 (Windows)
scripts/dev.sh (macOS/Linux)
docs/development-f5.md
```

Ao pressionar `F5`, o VS Code deverá:

1. Executar o Docker Compose de desenvolvimento.
2. Utilizar `.env.example`.
3. Construir imagens quando necessário.
4. Subir API, front-end, worker, PostgreSQL, Redis, n8n, armazenamento e Nginx.
5. Aguardar o health check.
6. Abrir `http://localhost/app`.

Disponibilize tarefas para iniciar sem rebuild, parar, reiniciar, consultar status e acompanhar logs.

O script deverá verificar Docker e Docker Desktop, usar caminhos relativos, funcionar no PowerShell (Windows) e Bash (macOS/Linux), e mostrar logs claros em caso de falha.

### Acesso administrativo local

No desenvolvimento, a tela de login poderá exibir `Acessar como administrador`.

Esse botão deverá:

* existir apenas quando uma variável explícita de desenvolvimento estiver habilitada;
* usar somente credenciais de bootstrap locais;
* nunca ser habilitado em produção;
* entrar com o papel Proprietário;
* receber as permissões empresariais instaladas;
* não expor senha em interface, logs ou código-fonte do front-end.

Variáveis sugeridas:

```text
VITE_DEV_ADMIN_LOGIN_ENABLED=true
VITE_DEV_ADMIN_EMAIL=admin@orkestral.dev.br
VITE_DEV_ADMIN_PASSWORD=valor-exclusivamente-local
```

O build de produção deverá ignorar ou rejeitar essa funcionalidade.

## Critérios de conclusão

* O projeto sobe com um único comando e também com `F5`.
* O navegador abre automaticamente após os serviços ficarem saudáveis.
* `/health` responde.
* Front-end, PostgreSQL e Redis funcionam.
* O README explica a execução.
* O acesso rápido existe somente localmente.
* Nenhum segredo real está versionado.
