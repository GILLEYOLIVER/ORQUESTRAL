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

## Ciclo empresarial 2 - contratos multiempresa e governanca

Data: 21 de julho de 2026.

- Fase atual: Fase 1 - Fundacao empresarial.
- Concluido neste recorte: contrato automatico de tabelas por tenant, contrato de seguranca das rotas, validacao rota versus catalogo de permissoes, inventario funcional e auditoria de multiempresa.
- Teste negativo adicionado: Empresa A nao consegue consultar nem excluir oportunidade, campanha, projeto ou agente da Empresa B.
- Migracoes: nenhuma; o ciclo protege o schema atual sem alterar dados.
- Risco externo: GitHub Actions nao inicia por restricao de pagamento/limite da conta e branch protection nao esta disponivel para este repositorio privado no plano atual.
- Regra de integracao: manter PR aberto ate os checks remotos aprovarem; nunca tornar o repositorio publico.
- Proximo passo exato: executar a bateria local do ciclo, publicar o PR e iniciar a auditoria de agentes, automacoes, integracoes e plugins.

### Evidencia de validacao do ciclo 2

- Ruff: 226 arquivos formatados e lint aprovado.
- MyPy: 165 arquivos de producao aprovados.
- Backend: 95 testes unitarios e 6 testes de integracao aprovados.
- Frontend: 9 testes, lint, tipos e build de producao aprovados.
- E2E: 5 aprovados e 2 ignorados por contrato de ambiente.
- Seguranca: auditoria concluida sem bloqueios.
- Runtime: 8 containers saudaveis; `/health`, `/ready` e `/app` aprovados.
- Banco: Alembic `20260720_0027 (head)` confirmado.

## Ciclo empresarial 3 - auditoria de runtime e pesquisa oficial

Data: 21 de julho de 2026.

- Agentes: Nivel 2; 2 provedores, 3 ferramentas tipadas, aprovacao e consumo presentes.
- Conhecimento: `pgvector` com vetores de 384 dimensoes confirmado.
- Automacoes: Nivel 3; 16 blocos e definicao canonica com versoes e rollback.
- Motor externo: n8n saudavel como container, mas API informa indisponivel e nao configurado.
- Plugins: 7 conectores catalogados com credenciais cifradas e ativacao por empresa.
- Pesquisa: fontes oficiais Salesforce Architects, Salesforce Developers e MuleSoft registradas com data.
- Maior lacuna: eventos transacionais, politicas versionadas de agentes, avaliacao, DLQ e governanca de APIs.
- Migracoes: nenhuma neste ciclo de diagnostico.
- Proximo passo exato: criar matriz de equivalencia detalhada, arquitetura-alvo e roadmap por dependencia.

## Ciclo empresarial 4 - matriz, arquitetura-alvo e roadmap

Data: 21 de julho de 2026.

- Matriz: 40 capacidades avaliadas com nivel, lacuna, solucao, fase e contrato de entrega.
- Arquitetura: monolito modular orientado por metadata, eventos e agentes controlados.
- Roadmap: Fases 0 a 12 ordenadas por dependencias e criterios de saida.
- Decisao imediata: concluir fundacao empresarial, eventos transacionais e base de metadata antes de ampliar autonomia.
- Migracoes: nenhuma neste ciclo de arquitetura.
- Proximo passo exato: implementar o primeiro recorte vertical de Fase 1 com Tenant Context, policy e auditoria/evento.

## Ciclo empresarial 5 - primeiro recorte fundamental de eventos

Data: 21 de julho de 2026.

- Banco: outbox transacional e ledger de consumo idempotente.
- Contrato: envelope versionado, classificado, limitado e sem chaves sensiveis.
- Producao real: acoes autorizadas geram evento na mesma transacao da auditoria.
- Entrega: task Celery publica lotes em Redis Stream por interface substituivel.
- Resiliencia: lock recuperavel, retry com backoff e dead-letter apos limite.
- Testes: schema, payload, publicacao e duplicidade de consumo.
- Migracao: `20260721_0028`.
- Proximo passo exato: validar migracao e suites; depois iniciar Tenant Context e Policy Engine.

### Evidencia de validacao do ciclo 5

- Ruff: 235 arquivos formatados e lint aprovado.
- MyPy: 171 arquivos aprovados.
- Backend: 100 testes unitarios aprovados.
- Integracao: 7 testes aprovados.
- Seguranca: auditoria concluida sem bloqueios.
- Migracao: `0028 -> 0027 -> 0028` aprovada; banco em `20260721_0028 (head)`.
- Worker: task registrada e execucao real aprovada com lote vazio.

## Ciclo empresarial 6 - contexto e Policy Engine

Data: 21 de julho de 2026.

- Contexto: empresa, ator e correlacao propagaveis para jobs sem snapshot de permissao.
- Policy: tenant, permissao, campos, risco e escopo de plataforma avaliados deterministicamente.
- Auditoria: ledger versionado de decisoes e evento transacional sem identificador cross-tenant.
- Integracao inicial: dispatcher de outbox vincula contexto por evento.
- Migracao: `20260721_0029`.
- Adocao: contrato criado; migracao das rotas sera incremental e mensurada.
- Proximo passo exato: validar o ciclo e aplicar Policy Engine ao primeiro dominio empresarial.

### Evidencia de validacao do ciclo 6

- Ruff: 231 arquivos formatados e lint aprovado.
- MyPy: 166 arquivos aprovados.
- Backend: 105 testes unitarios aprovados.
- Integracao: 8 testes aprovados.
- Seguranca: segredos, Actions, Node, Bandit e dependencias Python sem bloqueios.
- Migracao: `0029 -> 0028 -> 0029` aprovada; banco em `20260721_0029 (head)`.
- Proximo passo exato: aplicar a fundacao empresarial ao primeiro dominio e iniciar a plataforma de metadados.

## Ciclo empresarial 7 - fundacao da plataforma de metadados

Data: 21 de julho de 2026.

- Definicoes: entidades e campos normalizados, tipados e isolados por empresa.
- Versoes: rascunho, validacao, publicacao, retirada e checksum deterministico.
- API: listar, criar, consultar, editar rascunho, versionar, validar e publicar.
- Seguranca: permissoes dedicadas e Policy Engine aplicado ao primeiro dominio real.
- Rastreabilidade: auditoria e eventos transacionais para todas as alteracoes.
- Migracao: `20260721_0030`.
- Testes: contratos puros e ciclo completo entre duas empresas.
- Proximo passo exato: validar o ciclo e criar registros personalizados seguros sobre schemas publicados.

### Evidencia de validacao do ciclo 7

- Ruff: 240 arquivos formatados e lint aprovado.
- MyPy: 172 arquivos aprovados.
- Backend: 109 testes unitarios aprovados.
- Integracao: 9 testes aprovados.
- Seguranca: segredos, Actions, Node, Bandit e dependencias Python sem bloqueios.
- Migracao: `0030 -> 0029 -> 0030` aprovada; banco em `20260721_0030 (head)`.
- Isolamento: entidade de uma empresa retorna `404` para outra empresa.
- Eventos: auditoria e eventos de dominio possuem contratos distintos, sem duplicidade semantica.
