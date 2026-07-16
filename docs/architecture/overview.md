# Arquitetura da fundação

## Fluxo de execução

```mermaid
flowchart LR
    Browser["Navegador"] --> Gateway["Nginx gateway"]
    Gateway --> Web["React estático"]
    Gateway --> API["FastAPI"]
    API --> PostgreSQL[("PostgreSQL")]
    API --> Redis[("Redis")]
    API -. fases futuras .-> N8N["n8n interno"]
    API -. fases futuras .-> Storage["Objeto S3 compatível"]
    Worker["Celery worker"] --> Redis
    Worker --> PostgreSQL
    Worker -. fases futuras .-> Storage
    N8N --> PostgreSQL
```

O gateway é o único serviço publicado no Compose base. Redes internas independentes limitam a comunicação entre persistência, automação e armazenamento.

## Identidade e contexto multiempresa

```mermaid
sequenceDiagram
    participant Browser as Navegador
    participant API as FastAPI
    participant DB as PostgreSQL
    Browser->>API: POST /auth/login
    API->>DB: valida usuário, senha e vínculos
    API-->>Browser: access token em memória + refresh HttpOnly
    Browser->>API: Bearer access token
    API->>DB: valida sessão, empresa e vínculo
    API-->>Browser: resposta restrita ao company_id do contexto
```

O cliente nunca escolhe livremente um `company_id` para operações do tenant. A empresa atual vem da sessão autenticada e só é aceita quando existe vínculo ativo. O servidor carrega as permissões do papel nesse vínculo a cada requisição e aplica dependências explícitas como `require_permission("agents.create")`.

## Autorização

Papéis pertencem a uma única empresa e recebem permissões de um catálogo global imutável. “Proprietário” e “Membro” são criados automaticamente; papéis personalizados podem ser administrados no painel. A interface esconde ações indisponíveis com `PermissionGuard`, mas a decisão final sempre pertence à API. Toda criação, alteração ou exclusão de papel e toda mudança de papel de usuário gera um evento de auditoria sem credenciais ou segredos.

## Núcleo modular

O catálogo distingue módulos planejados de módulos efetivamente instalados. Somente manifests carregados pelo registro central podem ser ativados. Cada operação de um módulo exige simultaneamente a permissão do papel e um vínculo ativo em `company_modules`. O CRM é o primeiro módulo instalado e todo acesso a contatos deriva o `company_id` da sessão.

## Limites atuais

- Financeiro, suporte, RH, estoque, projetos, marketing e analytics aparecem como planejados, mas não podem ser ativados até possuírem implementação e manifest próprios.
- O worker executa somente uma tarefa de diagnóstico.
- n8n e armazenamento são provisionados, mas não possuem integração funcional com a API.
- O pacote de plugins está deliberadamente vazio até a Fase 5.

## Convenções

- Rotas tratam HTTP; serviços concentram casos de uso; repositórios futuros concentrarão acesso ao banco.
- Todos os erros HTTP seguem `ProblemDetails` e carregam `request_id`.
- Logs são JSON e não incluem corpo de requisição, credenciais ou mensagens cruas de exceções inesperadas.
- Dependências externas recebem timeout; readiness nunca retorna mensagens internas de erro.
- O gateway apresenta as APIs em `/api`; internamente a aplicação FastAPI mantém as rotas sem esse prefixo. Versionamento de módulos de negócio será introduzido quando necessário.
