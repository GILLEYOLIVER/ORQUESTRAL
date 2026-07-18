# DOCUMENTO MESTRE DE DESENVOLVIMENTO — ORKESTRAL

**Versão:** 1.2 — especificação integral com fluxo de desenvolvimento F5

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

Utilize a seguinte base tecnológica:

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
│
├── apps/
│   ├── api/
│   ├── web/
│   └── worker/
│
├── packages/
│   ├── shared-types/
│   ├── ui-components/
│   └── plugin-sdk/
│
├── infrastructure/
│   ├── docker/
│   ├── nginx/
│   ├── monitoring/
│   └── scripts/
│
├── docs/
│   ├── architecture/
│   ├── api/
│   ├── database/
│   ├── plugins/
│   └── decisions/
│
├── tests/
│   ├── integration/
│   ├── security/
│   └── end-to-end/
│
├── docker-compose.yml
├── docker-compose.development.yml
├── .env.example
├── .gitignore
├── README.md
└── Makefile
```

Dentro do back-end:

```text
apps/api/app/
│
├── main.py
├── core/
│   ├── config.py
│   ├── database.py
│   ├── security.py
│   ├── logging.py
│   ├── exceptions.py
│   └── tenancy.py
│
├── modules/
│   ├── authentication/
│   ├── companies/
│   ├── users/
│   ├── permissions/
│   ├── modules_catalog/
│   ├── plugins/
│   ├── integrations/
│   ├── workflows/
│   ├── agents/
│   ├── knowledge/
│   ├── billing/
│   ├── auditing/
│   └── notifications/
│
├── shared/
│   ├── domain/
│   ├── repositories/
│   ├── services/
│   ├── schemas/
│   └── utilities/
│
└── migrations/
```

Cada módulo do back-end deverá conter, quando aplicável:

```text
domain/
models/
schemas/
repositories/
services/
routes/
permissions/
tests/
```

Não concentre toda a aplicação em arquivos gigantes.

---

# 6. FASE 1 — FUNDAÇÃO DO PROJETO

## Objetivo

Criar uma base executável, organizada e documentada.

## Implementação no código

### 6.1 Criar o back-end

Crie a aplicação FastAPI em:

```text
apps/api/app/main.py
```

Implemente:

* inicialização da aplicação;
* carregamento das configurações;
* conexão com PostgreSQL;
* conexão com Redis;
* middleware de tratamento de erros;
* middleware de identificação de requisição;
* logs estruturados;
* rota de verificação de saúde.

Rotas iniciais:

```text
GET /health
GET /ready
```

`/health` deve confirmar que a API está ativa.

`/ready` deve verificar pelo menos:

* PostgreSQL;
* Redis;
* configurações obrigatórias.

### 6.2 Criar configuração central

Crie:

```text
apps/api/app/core/config.py
```

Leia configurações por variáveis de ambiente.

Exemplos:

```text
DATABASE_URL
REDIS_URL
JWT_SECRET
ENCRYPTION_KEY
N8N_BASE_URL
N8N_API_KEY
STORAGE_ENDPOINT
STORAGE_ACCESS_KEY
STORAGE_SECRET_KEY
```

Crie `.env.example` sem segredos reais.

### 6.3 Criar o front-end

Crie o projeto React com TypeScript em:

```text
apps/web/
```

Implemente inicialmente:

* estrutura de rotas;
* layout público;
* layout autenticado;
* página de login;
* página inicial provisória;
* página de erro;
* cliente HTTP;
* armazenamento seguro do estado da sessão;
* tratamento global de erros.

### 6.4 Criar Docker Compose

Configure os serviços:

```text
api
web
worker
postgres
redis
n8n
object-storage
nginx
```

O n8n deverá estar acessível somente pela rede interna, durante a operação de produção.

### 6.4.1 Experiência de desenvolvimento pelo VS Code (F5)

O repositório deverá incluir uma configuração compartilhada do VS Code para iniciar o ambiente de desenvolvimento com `F5`.

Arquivos obrigatórios:

```text
.vscode/launch.json
.vscode/tasks.json
scripts/dev.ps1 (Windows)
scripts/dev.sh (macOS/Linux)
```

Ao pressionar `F5`, o VS Code deverá:

1. executar o Docker Compose de desenvolvimento;
2. construir os serviços quando necessário;
3. aguardar o health check da aplicação;
4. abrir `http://localhost/app` em uma nova janela do navegador;
5. apresentar erros de inicialização no terminal integrado.

Deverão existir tarefas separadas para:

* iniciar com rebuild;
* iniciar sem rebuild;
* encerrar o ambiente;
* consultar o status;
* acompanhar logs dos serviços principais.

A configuração compartilhada do VS Code poderá ser versionada, mas arquivos pessoais, extensões locais, segredos e preferências individuais não deverão ser incluídos.

O front-end poderá oferecer a ação **Acessar como administrador** somente em ambiente de desenvolvimento local. Essa ação não deverá conter senha, token ou credencial embutida no código do navegador. O back-end deverá validar explicitamente o ambiente e rejeitar esse fluxo em testing, staging e production.

Critérios adicionais de conclusão:

* pressionar `F5` inicia o ambiente a partir da raiz do monorepositório;
* a interface é aberta automaticamente após o health check;
* o fluxo funciona no Windows PowerShell e no Bash (macOS/Linux);
* a configuração não expõe segredos;
* o acesso administrativo rápido fica indisponível fora do desenvolvimento local.

### 6.5 Criar migrações

Configure Alembic.

A primeira migração deverá criar extensões e estruturas básicas necessárias.

### Critérios de conclusão

* O projeto sobe com um único comando.
* A API responde em `/health`.
* O front-end abre sem erros.
* PostgreSQL e Redis são acessíveis.
* O README explica como executar o projeto.
* Nenhum segredo real está versionado.

---

# 7. FASE 2 — EMPRESAS, USUÁRIOS E AUTENTICAÇÃO

## Objetivo

Implementar a estrutura multiempresa e o acesso seguro.

## 7.1 Tabela de empresas

Crie a tabela `companies` com pelo menos:

```text
id
legal_name
trade_name
document_number
slug
status
timezone
language
created_at
updated_at
deleted_at
```

Use identificadores UUID.

O campo `slug` deve ser único.

O campo `status` pode aceitar:

```text
active
suspended
trial
cancelled
```

## 7.2 Tabela de usuários

Crie `users`:

```text
id
name
email
password_hash
status
is_platform_admin
last_login_at
created_at
updated_at
deleted_at
```

Não armazene senha em texto puro.

## 7.3 Relação entre empresas e usuários

Crie `company_users`:

```text
id
company_id
user_id
role_id
status
is_owner
created_at
updated_at
```

Um usuário poderá futuramente participar de mais de uma empresa.

## 7.4 Autenticação

Implemente:

```text
POST /auth/login
POST /auth/refresh
POST /auth/logout
POST /auth/forgot-password
POST /auth/reset-password
GET  /auth/me
```

Utilize:

* token de acesso de curta duração;
* token de renovação;
* revogação de sessões;
* armazenamento seguro dos tokens;
* limitação de tentativas de login;
* registro de tentativas suspeitas.

## 7.5 Contexto da empresa

Crie um componente central, por exemplo:

```text
core/tenancy.py
```

Esse componente deverá:

1. Identificar o usuário autenticado.
2. Identificar a empresa selecionada.
3. Validar se o usuário pertence à empresa.
4. Criar um objeto de contexto.
5. Disponibilizar `company_id`, `user_id`, papéis e permissões.

Exemplo:

```python
class RequestContext:
    user_id: UUID
    company_id: UUID
    role_ids: list[UUID]
    permissions: set[str]
```

## 7.6 Interface

Crie as telas:

* login;
* recuperação de senha;
* seleção de empresa, quando houver mais de uma;
* perfil do usuário;
* gestão de empresas para administradores da plataforma;
* gestão de usuários da empresa.

## Critérios de conclusão

* O usuário consegue entrar e sair.
* Um usuário comum não acessa outra empresa.
* O administrador da plataforma consegue cadastrar empresas.
* O proprietário da empresa consegue convidar usuários.
* Testes de isolamento multiempresa passam.

---

# 8. FASE 3 — PAPÉIS E PERMISSÕES

## Objetivo

Criar autorização granular e reutilizável.

## 8.1 Estrutura do banco

Crie:

### `roles`

```text
id
company_id
name
description
is_system_role
created_at
updated_at
```

### `permissions`

```text
id
code
module_code
action
description
```

### `role_permissions`

```text
role_id
permission_id
```

Exemplos de códigos:

```text
users.view
users.create
users.update
users.delete
agents.view
agents.create
agents.execute
agents.configure
workflows.view
workflows.execute
workflows.configure
integrations.manage
billing.view
billing.manage
```

## 8.2 Verificação no back-end

Crie uma dependência reutilizável:

```python
require_permission("agents.create")
```

Toda rota protegida deverá declarar sua permissão.

Não faça a autorização apenas escondendo botões no front-end.

## 8.3 Verificação no front-end

Crie um componente:

```text
PermissionGuard
```

Exemplo conceitual:

```tsx
<PermissionGuard permission="agents.create">
  <CreateAgentButton />
</PermissionGuard>
```

O front-end melhora a experiência, mas o back-end continua sendo a autoridade final.

## Critérios de conclusão

* Permissões são verificadas no servidor.
* O painel permite criar papéis personalizados.
* Alterações de permissões são auditadas.
* Existem testes para acessos permitidos e negados.

---

# 9. FASE 4 — NÚCLEO MODULAR

## Objetivo

Permitir que funcionalidades sejam ativadas separadamente por empresa.

## 9.1 Catálogo de módulos

Crie `modules_catalog`:

```text
id
code
name
description
version
category
is_core
status
configuration_schema
created_at
updated_at
```

Exemplos:

```text
crm
finance
support
human_resources
inventory
projects
marketing
analytics
```

## 9.2 Módulos ativados por empresa

Crie `company_modules`:

```text
id
company_id
module_id
status
configuration
activated_at
deactivated_at
```

## 9.3 Contrato de módulo

Cada módulo deverá registrar:

* código;
* nome;
* versão;
* permissões;
* rotas;
* menus;
* configurações;
* eventos publicados;
* eventos consumidos;
* migrações necessárias.

Crie um registro central que carregue apenas os módulos instalados.

## 9.4 Primeiro módulo: CRM básico

Implemente o primeiro módulo funcional.

Tabelas:

### `crm_contacts`

```text
id
company_id
name
email
phone
company_name
job_title
source
status
assigned_user_id
created_at
updated_at
deleted_at
```

### `crm_tags`

```text
id
company_id
name
created_at
```

### `crm_contact_tags`

```text
contact_id
tag_id
```

Rotas:

```text
GET    /crm/contacts
POST   /crm/contacts
GET    /crm/contacts/{id}
PATCH  /crm/contacts/{id}
DELETE /crm/contacts/{id}
```

Implemente:

* paginação;
* pesquisa;
* filtros;
* ordenação;
* exclusão lógica;
* auditoria;
* validação por empresa.

Telas:

* lista de contatos;
* cadastro;
* edição;
* detalhes;
* filtros;
* pesquisa;
* paginação.

## Critérios de conclusão

* O CRM pode ser ativado para uma empresa e desativado para outra.
* Empresa sem o módulo ativo não acessa as rotas.
* Contatos ficam isolados por empresa.
* O módulo possui testes próprios.

---

# 10. FASE 5 — SISTEMA DE PLUGINS

## Objetivo

Conectar serviços externos sem acoplar integrações ao núcleo.

## 10.1 SDK de plugins

Crie:

```text
packages/plugin-sdk/
```

Defina interfaces para:

* metadados;
* autenticação;
* configuração;
* ferramentas disponíveis;
* gatilhos;
* ações;
* teste de conexão;
* tratamento de erros;
* renovação de tokens;
* webhooks.

Exemplo conceitual:

```python
class PluginDefinition:
    code: str
    name: str
    version: str
    authentication_type: str
    configuration_schema: dict
    actions: list
    triggers: list
```

## 10.2 Registro de plugins

Crie:

### `plugins`

```text
id
code
name
version
status
manifest
created_at
updated_at
```

### `company_plugins`

```text
id
company_id
plugin_id
status
configuration
created_at
updated_at
```

### `integration_credentials`

```text
id
company_id
plugin_id
name
encrypted_credentials
status
expires_at
created_at
updated_at
```

## 10.3 Cofre de credenciais

Nunca salve tokens e senhas em texto puro.

Crie um serviço central para:

* criptografar;
* descriptografar apenas durante o uso;
* mascarar valores na interface;
* rotacionar chaves;
* registrar acesso administrativo;
* impedir que segredos apareçam nos logs.

## 10.4 Primeiros plugins

Implemente inicialmente:

1. Webhook genérico.
2. E-mail SMTP.
3. E-mail IMAP ou provedor por API.
4. Google Calendar.
5. WhatsApp Business por provedor oficial.
6. PostgreSQL externo.
7. API REST genérica.

Cada plugin deve possuir a ação “Testar conexão”.

## Critérios de conclusão

* Plugins podem ser ativados por empresa.
* Credenciais ficam criptografadas.
* Um plugin com erro não derruba a aplicação inteira.
* O sistema registra falhas e tentativas de conexão.
* Novos plugins podem ser adicionados sem modificar o núcleo principal.

---

# 11. FASE 6 — INTEGRAÇÃO COM N8N

## Objetivo

Utilizar o n8n como motor interno de execução, sem expô-lo ao cliente.

## 11.1 Serviço de comunicação

Crie:

```text
modules/workflows/services/n8n_client.py
```

Esse cliente deverá centralizar:

* autenticação com n8n;
* criação de workflows;
* atualização;
* ativação;
* desativação;
* execução;
* consulta de status;
* consulta de histórico;
* tratamento de erros;
* timeouts;
* tentativas controladas.

Nenhuma rota deverá chamar o n8n diretamente sem passar por esse serviço.

## 11.2 Mapeamento interno

Crie `workflows`:

```text
id
company_id
name
description
status
version
definition
n8n_workflow_id
created_by
created_at
updated_at
```

Crie `workflow_executions`:

```text
id
company_id
workflow_id
external_execution_id
status
started_at
finished_at
input_summary
output_summary
error_summary
created_at
```

## 11.3 Segurança

Inclua o identificador interno da empresa em toda execução.

Não permita que um webhook público execute um workflow sem:

* assinatura;
* chave;
* token;
* limite de frequência;
* validação de empresa;
* validação do workflow.

## 11.4 Interface da Orkestral

Crie telas para:

* listar automações;
* criar automação;
* ativar e desativar;
* executar manualmente;
* visualizar histórico;
* visualizar erros;
* duplicar;
* importar modelo;
* exportar definição segura.

O cliente não deve ver URLs administrativas, credenciais ou termos técnicos desnecessários do n8n.

## Critérios de conclusão

* A Orkestral cria e executa um fluxo no n8n.
* O usuário acompanha o resultado pela Orkestral.
* O n8n não fica exposto ao usuário final.
* Falhas são registradas e apresentadas de maneira compreensível.

---

# 12. FASE 7 — AGENTES DE INTELIGÊNCIA ARTIFICIAL

## Objetivo

Permitir vários agentes por empresa, cada um com função, limites e ferramentas próprias.

## 12.1 Estrutura de agentes

Crie `agents`:

```text
id
company_id
name
description
system_instructions
status
model_provider
model_name
temperature
maximum_output_tokens
memory_enabled
knowledge_enabled
created_by
created_at
updated_at
```

Crie `agent_tools`:

```text
id
company_id
agent_id
tool_code
plugin_id
permissions
configuration
status
created_at
updated_at
```

Crie `agent_conversations`:

```text
id
company_id
agent_id
user_id
title
status
created_at
updated_at
```

Crie `agent_messages`:

```text
id
company_id
conversation_id
role
content
token_input
token_output
estimated_cost
created_at
```

## 12.2 Provedores de IA

Crie uma abstração:

```python
class LanguageModelProvider:
    async def generate(...)
    async def stream(...)
    async def calculate_usage(...)
```

Implemente os provedores em adaptadores separados.

O agente não deverá depender diretamente de uma empresa específica de IA.

## 12.3 Execução de ferramentas

A IA não deve executar código ou alterar dados diretamente.

Ela deverá solicitar o uso de uma ferramenta registrada.

Fluxo:

1. O usuário envia a solicitação.
2. O agente interpreta.
3. O modelo solicita uma ferramenta.
4. O back-end verifica a permissão.
5. O sistema valida os argumentos.
6. A ferramenta é executada.
7. O resultado retorna ao agente.
8. O agente produz a resposta final.
9. A operação é registrada na auditoria.

## 12.4 Confirmação para ações sensíveis

Ações como estas devem exigir confirmação:

* excluir registros;
* enviar cobranças;
* emitir pedidos;
* cancelar operações;
* enviar mensagens em massa;
* alterar dados financeiros;
* aprovar pagamentos;
* modificar permissões;
* executar uma automação crítica.

Crie estados de execução:

```text
requested
awaiting_confirmation
approved
rejected
executing
completed
failed
```

## 12.5 Controle de consumo

Registre:

* empresa;
* usuário;
* agente;
* provedor;
* modelo;
* tokens de entrada;
* tokens de saída;
* custo estimado;
* ferramenta utilizada;
* duração;
* resultado.

## Critérios de conclusão

* Uma empresa consegue cadastrar vários agentes.
* Cada agente possui ferramentas próprias.
* Um agente não acessa ferramentas não autorizadas.
* Custos e tokens são registrados.
* Ações sensíveis exigem confirmação.

---

# 13. FASE 8 — BASE DE CONHECIMENTO

## Objetivo

Permitir que agentes consultem documentos da empresa.

## 13.1 Estrutura

Crie `knowledge_bases`:

```text
id
company_id
name
description
status
created_at
updated_at
```

Crie `knowledge_documents`:

```text
id
company_id
knowledge_base_id
name
file_type
storage_key
processing_status
checksum
metadata
created_at
updated_at
```

Crie `knowledge_chunks`:

```text
id
company_id
document_id
content
chunk_index
metadata
embedding_reference
created_at
```

## 13.2 Processamento

Implemente tarefas assíncronas para:

1. receber o arquivo;
2. validar tipo e tamanho;
3. verificar segurança;
4. armazenar o original;
5. extrair o texto;
6. dividir o conteúdo em partes;
7. gerar representações vetoriais;
8. armazenar metadados;
9. marcar o documento como pronto;
10. registrar erros.

## 13.3 Tipos iniciais

Suporte inicialmente:

* PDF;
* DOCX;
* TXT;
* CSV;
* XLSX;
* páginas web autorizadas.

## 13.4 Consulta

O agente deverá:

1. receber a pergunta;
2. identificar a base de conhecimento autorizada;
3. pesquisar apenas documentos da empresa;
4. recuperar trechos relevantes;
5. enviar os trechos ao modelo;
6. responder;
7. registrar quais documentos foram consultados.

## Critérios de conclusão

* Arquivos são processados em segundo plano.
* Documentos de uma empresa não aparecem para outra.
* O agente responde usando documentos autorizados.
* O sistema informa as fontes internas utilizadas.
* Documentos podem ser removidos e reprocessados.

---

# 14. FASE 9 — CONSTRUTOR VISUAL DE AUTOMAÇÕES

## Objetivo

Permitir que usuários criem fluxos sem acessar diretamente o n8n.

## 14.1 Componentes visuais

Crie blocos próprios da Orkestral:

* gatilho manual;
* gatilho por horário;
* webhook;
* mensagem recebida;
* novo contato;
* condição;
* espera;
* repetição;
* consulta;
* atualização;
* envio de e-mail;
* envio de mensagem;
* execução de agente;
* aprovação humana;
* chamada de plugin;
* encerramento.

## 14.2 Estrutura do fluxo

Armazene uma definição neutra da Orkestral.

Exemplo:

```json
{
  "nodes": [],
  "connections": [],
  "variables": {},
  "version": 1
}
```

Crie um compilador interno que converta a definição da Orkestral para o formato necessário pelo n8n.

Não armazene apenas a definição do n8n, pois isso tornaria a plataforma dependente do formato interno dele.

## 14.3 Validação

Antes de publicar, valide:

* blocos desconectados;
* ciclos inválidos;
* credenciais ausentes;
* permissões;
* campos obrigatórios;
* ferramentas desativadas;
* risco de execução em massa;
* ausência de tratamento de erro.

## 14.4 Versionamento

Cada publicação deve gerar uma versão.

Implemente:

* rascunho;
* versão publicada;
* histórico;
* restauração;
* comparação;
* duplicação.

## Critérios de conclusão

* O usuário cria um fluxo visual.
* A definição é validada.
* O fluxo é convertido e publicado no n8n.
* O histórico de versões é preservado.
* O usuário consegue acompanhar cada execução.

---

# 15. FASE 10 — DASHBOARDS E RELATÓRIOS

## Objetivo

Apresentar resultados empresariais e operacionais.

## Métricas iniciais

* automações executadas;
* automações com sucesso;
* automações com falha;
* tempo economizado estimado;
* agentes mais utilizados;
* tokens consumidos;
* custo de IA;
* integrações com falha;
* usuários ativos;
* documentos processados;
* tarefas aguardando aprovação.

## Implementação

Crie um módulo de métricas que receba eventos internos.

Evite fazer consultas pesadas diretamente nas tabelas operacionais a cada abertura do dashboard.

Utilize:

* agregações periódicas;
* cache;
* tabelas de resumo;
* filtros por período;
* filtros por módulo;
* filtros por agente;
* filtros por workflow.

Permita exportação em:

* CSV;
* XLSX;
* PDF, quando apropriado.

---

# 16. FASE 11 — AUDITORIA E SEGURANÇA

## Objetivo

Registrar ações importantes e proteger o sistema.

## 16.1 Auditoria

Crie `audit_events`:

```text
id
company_id
user_id
actor_type
action
resource_type
resource_id
before_data
after_data
ip_address
user_agent
request_id
created_at
```

Não registre senhas, tokens ou credenciais completas.

## 16.2 Proteções

Implemente:

* rate limiting;
* bloqueio por tentativas;
* validação de entrada;
* proteção contra injeção;
* política de CORS;
* cabeçalhos de segurança;
* expiração de sessão;
* revogação de tokens;
* criptografia de credenciais;
* rotação de segredos;
* backup;
* recuperação de desastre;
* verificação de uploads;
* limites por plano;
* logs sem dados sensíveis.

## 16.3 Exclusão lógica

Use exclusão lógica para registros importantes.

Crie rotinas administrativas para exclusão definitiva conforme políticas e legislação aplicável.

---

# 17. FASE 12 — PLANOS, ASSINATURAS E LIMITES

## Objetivo

Permitir comercialização como SaaS.

## Estrutura

Crie:

### `plans`

```text
id
name
description
price
billing_cycle
limits
status
created_at
updated_at
```

### `subscriptions`

```text
id
company_id
plan_id
status
started_at
trial_ends_at
current_period_start
current_period_end
cancelled_at
created_at
updated_at
```

### `usage_records`

```text
id
company_id
metric
quantity
reference_date
metadata
created_at
```

Limites possíveis:

* número de usuários;
* número de agentes;
* número de automações;
* execuções mensais;
* tokens;
* armazenamento;
* integrações;
* documentos;
* chamadas de API.

A aplicação deverá verificar limites antes da execução e produzir mensagens claras.

---

# 18. FASE 13 — NOTIFICAÇÕES E APROVAÇÕES

## Objetivo

Criar uma central de eventos que exigem atenção humana.

Crie:

* notificações internas;
* notificações por e-mail;
* notificações por WhatsApp, quando autorizado;
* central de aprovações;
* lembretes;
* estados de leitura;
* preferências por usuário.

Tabelas:

```text
notifications
notification_preferences
approval_requests
approval_actions
```

O sistema deverá permitir que uma automação pause até a aprovação humana.

---

# 19. FASE 14 — TESTES

## Testes obrigatórios

### Testes unitários

* serviços;
* regras de negócio;
* permissões;
* validações;
* compilador de workflows;
* cálculo de limites;
* cálculo de consumo.

### Testes de integração

* PostgreSQL;
* Redis;
* armazenamento;
* n8n;
* provedores de IA;
* plugins.

### Testes de segurança

* acesso entre empresas;
* escalonamento de privilégio;
* rotas sem autorização;
* manipulação de IDs;
* upload malicioso;
* vazamento de credenciais.

### Testes de ponta a ponta

1. Criar empresa.
2. Criar usuário.
3. Ativar módulo.
4. Configurar plugin.
5. Criar agente.
6. Adicionar ferramenta.
7. Criar automação.
8. Executar.
9. Verificar logs.
10. Verificar consumo.

Não considere uma fase concluída sem testes automatizados.

---

# 20. FASE 15 — CI/CD E DEPLOY

## Pipeline

Configure o GitHub Actions para:

1. instalar dependências;
2. validar formatação;
3. executar análise estática;
4. executar testes;
5. verificar migrações;
6. construir imagens Docker;
7. verificar vulnerabilidades;
8. publicar imagens;
9. implantar no ambiente autorizado.

## Ambientes

Mantenha:

```text
development
testing
staging
production
```

Cada ambiente deve ter:

* banco separado;
* credenciais separadas;
* configurações separadas;
* domínio separado;
* logs separados.

## Deploy

Configure:

* Nginx;
* HTTPS;
* renovação automática de certificados;
* backups;
* monitoramento;
* health checks;
* política de reinicialização;
* migração controlada do banco;
* rollback.

---

# 21. ORDEM EXATA DE EXECUÇÃO PARA O CODEX

Implemente na seguinte ordem:

1. Criar monorepositório.
2. Configurar Docker e ambientes.
3. Criar API e health checks.
4. Criar front-end e layouts.
5. Configurar PostgreSQL, Redis e migrações.
6. Criar empresas.
7. Criar usuários.
8. Criar autenticação.
9. Criar contexto multiempresa.
10. Criar papéis e permissões.
11. Criar catálogo de módulos.
12. Criar ativação de módulos por empresa.
13. Implementar CRM básico como módulo de referência.
14. Criar SDK de plugins.
15. Implementar cofre de credenciais.
16. Criar plugins iniciais.
17. Criar cliente interno do n8n.
18. Criar workflows e histórico de execuções.
19. Criar agentes.
20. Criar abstração de provedores de IA.
21. Criar ferramentas dos agentes.
22. Criar confirmação de ações sensíveis.
23. Criar controle de tokens e custos.
24. Criar base de conhecimento.
25. Criar processamento assíncrono de documentos.
26. Criar construtor visual.
27. Criar compilador Orkestral para n8n.
28. Criar dashboards.
29. Criar auditoria.
30. Criar planos e assinaturas.
31. Criar central de notificações e aprovações.
32. Criar testes completos.
33. Criar pipeline CI/CD.
34. Preparar staging.
35. Executar auditoria de segurança.
36. Preparar produção.

---

# 22. REGRA DE ENTREGA DE CADA FASE

Ao concluir uma fase, apresente:

1. Resumo do que foi implementado.
2. Lista de arquivos criados.
3. Lista de arquivos alterados.
4. Migrações criadas.
5. Rotas adicionadas.
6. Variáveis de ambiente necessárias.
7. Testes criados.
8. Comandos para executar.
9. Possíveis limitações.
10. Próxima fase recomendada.

Não avance deixando erros conhecidos escondidos.

Não utilize dados fictícios silenciosamente em produção.

Não substitua integrações reais por simulações sem identificar claramente que são simulações.

---

# 23. PADRÕES OBRIGATÓRIOS DE CÓDIGO

* Utilize tipagem.
* Separe regras de negócio das rotas.
* Use repositórios para acesso ao banco.
* Use serviços para casos de uso.
* Evite importações circulares.
* Não coloque credenciais no código.
* Não misture dados entre empresas.
* Não permita que o front-end controle permissões reais.
* Não acople agentes diretamente a provedores.
* Não acople o sistema diretamente ao formato interno do n8n.
* Documente decisões importantes.
* Crie migrações reversíveis quando possível.
* Mantenha compatibilidade com versões anteriores das APIs.
* Utilize identificadores UUID.
* Registre erros com identificador de requisição.
* Nunca registre segredos completos.
* Adicione testes a cada funcionalidade.

---

# 24. RESULTADO FINAL ESPERADO

Ao final do projeto, a Orkestral deverá permitir que uma nova empresa:

1. Crie sua conta.
2. Cadastre usuários.
3. Configure permissões.
4. Escolha um plano.
5. Ative módulos.
6. Conecte serviços externos.
7. Cadastre agentes de IA.
8. Autorize ferramentas para cada agente.
9. Importe documentos.
10. Crie automações visualmente.
11. Execute tarefas por comandos em linguagem natural.
12. Aprove ações sensíveis.
13. Acompanhe execuções, consumo e custos.
14. Consulte dashboards e relatórios.
15. Expanda o sistema com novos módulos e plugins.

A complexidade técnica deverá permanecer escondida do cliente final.

A interface deverá usar termos empresariais simples.

A arquitetura deverá continuar modular, segura e reutilizável para empresas de diferentes segmentos.

Este documento deverá ser tratado como a especificação principal do repositório Orkestral.
