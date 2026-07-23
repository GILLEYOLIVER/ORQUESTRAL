# Auditoria de multiempresa e autorizacao

Data da auditoria: 21 de julho de 2026.

## Objetivo

Verificar se dados empresariais, rotas e permissoes do Orkestral possuem limites claros por empresa. Esta auditoria combina inspecao do metadata SQLAlchemy, introspeccao das dependencias FastAPI e testes reais com duas empresas.

## Resultado executivo

O isolamento atual e consistente no nivel da aplicacao: tabelas empresariais diretas usam `company_id`, rotas filtram pelo contexto autenticado e operacoes administrativas exigem permissoes. O ciclo adiciona contratos automaticos que impedem novos modelos ou rotas de escaparem silenciosamente dessas regras.

A defesa agora inclui PostgreSQL RLS em todas as tabelas com `company_id` e nas
duas associacoes protegidas pelo pai. Relacoes entre registros empresariais
normalmente ainda usam uma chave estrangeira pelo identificador e uma coluna
`company_id` separada. A aplicacao valida os dois lados, mas o banco ainda nao
possui chaves compostas em todos esses relacionamentos. Esse ponto permanece
como defesa em profundidade planejada, sem afirmar seguranca absoluta.

## Contrato das tabelas

Todas as tabelas empresariais diretas devem possuir:

- `company_id` obrigatorio;
- indice na coluna `company_id`;
- chave estrangeira para `companies.id`;
- exclusao em cascata quando a empresa for eliminada de forma autorizada.

Excecao deliberada:

- `audit_events.company_id` aceita nulo e usa `SET NULL`, permitindo eventos de plataforma sem empresa e preservando rastreabilidade apos a remocao controlada de um tenant.

Tabelas globais permitidas:

- `companies`;
- `users`;
- `auth_attempts`;
- `auth_sessions`;
- `password_reset_tokens`;
- `permissions`;
- `plans`;
- `plugins`;
- `modules_catalog`;
- `metric_aggregation_runs`.

Associacoes protegidas pelos pais:

- `crm_contact_tags`;
- `role_permissions`.

Qualquer nova tabela sem `company_id` quebra o teste ate ser classificada conscientemente. Isso evita que uma omissao seja aceita por acidente.

## Contrato das rotas

As dependencias FastAPI foram analisadas em tempo de execucao.

- Escritas empresariais exigem `permission_dependency` ou `require_platform_admin`.
- Leituras nao publicas exigem `get_current_principal`.
- Toda permissao declarada por rota precisa existir no catalogo central.
- Preferencias e leitura de notificacoes sao operacoes pessoais autenticadas e limitadas ao usuario atual.
- O webhook de automacoes nao usa sessao humana; ele permanece numa lista explicita porque e autenticado por segredo e assinatura do fluxo.
- Login, recuperacao e aceite de convite permanecem publicos por necessidade funcional, com controles proprios.

## Teste negativo entre empresas

O teste de integracao cria duas empresas independentes, com proprietarios diferentes, e ativa os mesmos modulos. A Empresa B cria:

- uma oportunidade de CRM;
- uma campanha de marketing;
- um projeto;
- um agente.

A Empresa A tenta consultar e excluir esses identificadores. O resultado exigido e `404`, evitando leitura, alteracao e enumeracao de registros. Em seguida, a Empresa B confirma que todos continuam acessiveis.

## Riscos registrados

| Risco                                                      | Severidade | Situacao             | Tratamento                                                         |
| ---------------------------------------------------------- | ---------- | -------------------- | ------------------------------------------------------------------ |
| Nova tabela empresarial sem `company_id`                   | Critica    | Mitigado neste ciclo | Contrato automatico de metadata                                    |
| Nova rota de escrita sem permissao                         | Critica    | Mitigado neste ciclo | Contrato automatico de dependencias                                |
| Codigo de permissao inexistente no catalogo                | Alta       | Mitigado neste ciclo | Comparacao automatica rota versus catalogo                         |
| Chave estrangeira entre tenants sem composicao por empresa | Alta       | Parcial              | Validacao na aplicacao; planejar constraints compostas por dominio |
| Ausencia de PostgreSQL RLS                                 | Alta       | Mitigado no ciclo 74 | Papeis transacionais, FORCE RLS e testes SQL negativos             |
| Cobertura negativa ainda nao inclui todo endpoint          | Media      | Parcial              | Expandir matriz a cada ciclo de dominio                            |
| Administrador de plataforma com alto privilegio            | Alta       | Controlado           | Auditoria, menor privilegio, MFA/SSO e segregacao futura           |

## Proximas melhorias obrigatorias

1. Separar credenciais PostgreSQL de migracao, API e worker.
2. Adicionar chaves compostas por tenant nos relacionamentos de maior risco.
3. Expandir testes negativos para conhecimento, estoque, financeiro, RH, analytics, plugins, billing e workflows.
4. Adicionar autorizacao por registro e por campo na plataforma de metadados.
5. Aplicar politica de retencao e eliminacao verificavel por dominio.
6. Integrar SAST, dependencia, segredo e DAST a uma pipeline executavel.

## Evidencias automatizadas

- `apps/api/tests/test_enterprise_security_contracts.py`
- `tests/integration/test_enterprise_tenant_boundaries.py`
- `tests/integration/test_postgresql_rls_penetration.py`
- `tests/integration/test_support_module.py`
- testes existentes de autenticacao, autorizacao, CRM e eliminacao de empresa.
