# Status de Implementacao Empresarial do Orkestral

Atualizado em: 21 de julho de 2026

## Fase atual

**Fase 0 - Descoberta e estabilizacao**

O primeiro ciclo do Prompt Mestre concluiu os itens imediatos 1 a 3:

1. inventario inicial do repositorio;
2. confirmacao da arquitetura real;
3. execucao e estabilizacao das suites existentes.

Progresso realista da Fase 0: **30%**.

Progresso realista do roteiro empresarial completo: **8%**.

Esses percentuais medem os criterios do novo Prompt Mestre, nao as fases historicas do Documento Mestre anterior.

## Estado comprovado

### Arquitetura

- Monorepo com API FastAPI, web React/TypeScript, worker Celery e pacotes compartilhados.
- Monolito modular no back-end, com dominios separados em `apps/api/app/modules`.
- PostgreSQL com `pgvector`, Redis, n8n, MinIO e Nginx executados por Docker Compose.
- Definicao canonica propria de workflows, compilada para n8n por adaptador.
- Registro de modulos com manifestos, permissoes, menus, eventos declarados e migracoes.
- RBAC por empresa, contexto autenticado e filtros `company_id` nas rotas analisadas.
- Cofre de credenciais e criptografia autenticada para campos sensiveis.
- Auditoria estruturada com redacao de chaves sensiveis.

### Servicos locais

Os oito servicos estavam ativos e saudaveis na verificacao de 21 de julho de 2026:

- `api`;
- `web`;
- `worker`;
- `postgres`;
- `redis`;
- `n8n`;
- `object-storage`;
- `nginx`.

Os endpoints `/health`, `/ready` e `/app` responderam corretamente. O banco local atingiu a revisao Alembic `20260720_0027`.

### Modulos instalados

- Analytics;
- CRM;
- Financeiro;
- Recursos Humanos;
- Estoque;
- Marketing;
- Projetos;
- Suporte.

Agentes, conhecimento, automacoes, plugins, notificacoes, billing, identidade e auditoria fazem parte do nucleo, mas ainda nao satisfazem todos os criterios empresariais do novo roteiro.

## Recursos concluidos neste ciclo

- Prompt Mestre empresarial registrado na raiz do repositorio.
- Inventario inicial de estrutura, runtime, CI, modulos, rotas, modelos e testes.
- Contrato central de modelos atualizado para incluir as expansoes de CRM, marketing, suporte e projetos.
- Contrato de migracoes dos manifestos atualizado nos testes.
- Tipagem SQLAlchemy corrigida em revogacao de sessoes, concorrencia otimista e exclusao de dependencias.
- Artefatos OpenAPI e tipos TypeScript regenerados para as APIs adicionadas.
- Migracoes `0024` a `0027` aplicadas no ambiente local.
- Cadeia completa de migracoes validada em banco temporario isolado: base, `head`, base e `head` novamente.

## Recursos parciais

- Isolamento multiempresa: aplicado por contexto e filtros, mas ainda sem matriz completa de testes por dominio nem decisao final sobre RLS.
- Permissoes: RBAC por modulo/acao existe; seguranca por registro e campo ainda nao existe como plataforma geral.
- Auditoria: ha dois mecanismos historicos que precisam ser unificados.
- Eventos: manifestos declaram eventos, mas nao ha transactional outbox nem entrega idempotente.
- Agentes: chat, ferramentas, aprovacao, uso e provedores existem; faltam versoes, politicas completas, autonomia configuravel, suites de avaliacao e observabilidade empresarial.
- Metadados: manifestos de modulo existem; ainda nao ha entidades, campos, layouts e registros personalizados publicaveis.
- Plugins: catalogo, credenciais e testes existem; ainda nao ha assinatura, isolamento de codigo e ciclo de pacotes empresarial.

## Pendencias estruturais prioritarias

1. Auditoria formal de isolamento e permissoes em todos os dominios.
2. Matriz de equivalencia baseada em fontes oficiais atuais.
3. Arquitetura-alvo e roadmap por dependencias.
4. Transactional outbox com consumidores idempotentes e DLQ.
5. Fundacao versionada da plataforma de metadados.
6. Politicas e versionamento do runtime de agentes.
7. Seguranca por registro e campo.
8. Observabilidade distribuida e limites por empresa.

## Migracoes deste ciclo

- `20260720_0024`: pipelines, etapas, oportunidades e atividades comerciais.
- `20260720_0025`: desempenho, experimentos e atribuicao de marketing.
- `20260720_0026`: filas, SLA, eventos e satisfacao de suporte.
- `20260720_0027`: portfolios, marcos, riscos, membros, dependencias e exclusao segura por empresa.

## Verificacoes executadas

| Verificacao               | Resultado                                                                  |
| ------------------------- | -------------------------------------------------------------------------- |
| Ruff lint                 | aprovado                                                                   |
| Ruff format               | aprovado apos formatacao dos arquivos novos                                |
| MyPy                      | 187 arquivos aprovados                                                     |
| Pytest unitario           | 91 aprovados                                                               |
| Pytest integracao         | 5 aprovados                                                                |
| Front-end lint            | aprovado                                                                   |
| Front-end tipos           | aprovado                                                                   |
| Front-end unitario        | 9 aprovados                                                                |
| Front-end build           | aprovado, com alerta de bundle acima de 500 kB                             |
| Playwright E2E            | 5 aprovados e 2 ignorados por dependerem do compose de contrato da Fase 14 |
| Auditoria de seguranca    | aprovada sem vulnerabilidade conhecida bloqueante                          |
| Health/readiness/app      | aprovados                                                                  |
| Alembic upgrade/downgrade | aprovado em banco temporario isolado                                       |

## Riscos e divida tecnica

- O bundle principal web tem aproximadamente 836 kB antes de gzip e precisa de divisao por rotas.
- O `httpx` usado por `TestClient` emite aviso de depreciacao futura.
- O ambiente local usa volume persistente com senha diferente do valor padrao de host; scripts de integracao devem resolver o endpoint correto sem expor o segredo.
- Dois testes E2E de contrato exigem `docker-compose.test.yml` e nao foram executados no comando E2E reduzido.
- Expansoes recentes ainda precisam de testes de integracao dedicados para CRM comercial, performance de marketing, operacoes de suporte, portfolios e exclusao de empresa.
- A exclusao de tenant nao apaga copias de backup imediatamente; a politica de retencao e destruicao criptografica precisa ser formalizada.
- RLS ainda nao foi ativado e nao deve ser ativado sem ADR, testes de workers/migracoes/admin e analise de desempenho.

## Proximo passo exato

Iniciar o ciclo 2 com os itens imediatos 4 a 6:

1. registrar formalmente o estado e dependencias dos containers;
2. concluir o inventario funcional de cada modulo;
3. executar auditoria sistematica de multiempresa e permissoes, incluindo testes negativos entre empresas.

Depois dos tres itens, publicar e mesclar o segundo PR somente com os checks obrigatorios aprovados.
