# DOCUMENTO MESTRE — FASES 2 A 5

# 7. FASE 2 — EMPRESAS, USUÁRIOS E AUTENTICAÇÃO

## Objetivo

Implementar a estrutura multiempresa e o acesso seguro.

## Estrutura principal

Crie `companies`, `users` e `company_users` com UUID, timestamps, status e exclusão lógica quando aplicável.

A empresa deve possuir nome legal, nome comercial, documento, slug único, status, fuso horário e idioma. Usuários devem possuir nome, e-mail, hash de senha, status, indicador de administrador da plataforma e último acesso.

A relação `company_users` deve permitir que um usuário participe futuramente de mais de uma empresa, com papel, status e indicador de proprietário.

## Autenticação

Implemente:

```text
POST /auth/login
POST /auth/refresh
POST /auth/logout
POST /auth/forgot-password
POST /auth/reset-password
GET  /auth/me
```

Utilize token de acesso curto, refresh token, revogação de sessões, armazenamento seguro, limitação de tentativas e registro de acessos suspeitos.

## Contexto da empresa

Crie `core/tenancy.py` para identificar usuário e empresa, validar vínculo e disponibilizar `company_id`, `user_id`, papéis e permissões. Nunca aceite `company_id` do front-end como fonte confiável.

## Interface

Inclua login, recuperação de senha, seleção de empresa, perfil, gestão de empresas para administrador da plataforma e gestão de usuários para proprietários.

## Critérios de conclusão

- Entrada e saída funcionam.
- Usuário comum não acessa outra empresa.
- Administrador da plataforma cadastra empresas.
- Proprietário convida usuários.
- Testes de isolamento multiempresa passam.

---

# 8. FASE 3 — PAPÉIS E PERMISSÕES

## Objetivo

Criar autorização granular e reutilizável.

## Banco

Crie:

```text
roles
permissions
role_permissions
```

`roles` pertence à empresa. `permissions` possui código, módulo, ação e descrição. `role_permissions` relaciona ambos.

Exemplos de permissões:

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

## Back-end

Crie uma dependência reutilizável como:

```python
require_permission("agents.create")
```

Toda rota protegida deve declarar a permissão. O servidor é a autoridade final.

## Front-end

Crie `PermissionGuard` para melhorar a experiência sem substituir a verificação do back-end.

## Critérios de conclusão

- Permissões são verificadas no servidor.
- Papéis personalizados podem ser criados.
- Alterações são auditadas.
- Há testes de acessos permitidos e negados.

---

# 9. FASE 4 — NÚCLEO MODULAR

## Objetivo

Permitir ativar funcionalidades separadamente por empresa.

## Catálogo

Crie `modules_catalog` com código, nome, descrição, versão, categoria, indicador de núcleo, status e schema de configuração.

Crie `company_modules` com empresa, módulo, status, configuração e datas de ativação/desativação.

Cada módulo registra código, nome, versão, permissões, rotas, menus, configurações, eventos e migrações. O registro central deve carregar apenas módulos instalados.

## CRM básico

Implemente o primeiro módulo funcional com:

```text
crm_contacts
crm_tags
crm_contact_tags
```

Rotas:

```text
GET    /crm/contacts
POST   /crm/contacts
GET    /crm/contacts/{id}
PATCH  /crm/contacts/{id}
DELETE /crm/contacts/{id}
```

Inclua paginação, pesquisa, filtros, ordenação, exclusão lógica, auditoria e isolamento por empresa.

Telas: lista, cadastro, edição, detalhes, filtros, pesquisa e paginação.

## Critérios de conclusão

- CRM pode ser ativado para uma empresa e desativado para outra.
- Empresa sem o módulo não acessa as rotas.
- Contatos ficam isolados.
- O módulo possui testes próprios.

---

# 10. FASE 5 — SISTEMA DE PLUGINS

## Objetivo

Conectar serviços externos sem acoplar integrações ao núcleo.

## SDK

Crie `packages/plugin-sdk/` e defina interfaces para metadados, autenticação, configuração, ferramentas, gatilhos, ações, teste de conexão, erros, renovação de tokens e webhooks.

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

## Persistência

Crie:

```text
plugins
company_plugins
integration_credentials
```

Credenciais devem ser vinculadas à empresa, criptografadas e nunca devolvidas em texto puro.

## Cofre de credenciais

O serviço central deve criptografar, descriptografar apenas durante o uso, mascarar valores, permitir rotação de chaves, registrar acessos administrativos e impedir segredos nos logs.

## Plugins iniciais

1. Webhook genérico.
2. E-mail SMTP.
3. E-mail IMAP ou API.
4. Google Calendar.
5. WhatsApp Business oficial.
6. PostgreSQL externo.
7. API REST genérica.

Cada plugin deve oferecer `Testar conexão` com timeout e erro controlado.

## Critérios de conclusão

- Plugins são ativados por empresa.
- Credenciais ficam criptografadas.
- Falha de plugin não derruba a aplicação.
- Tentativas e falhas são registradas.
- Novos plugins podem ser adicionados sem modificar o núcleo.
