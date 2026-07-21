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

## Ciclo empresarial 8 - registros personalizados seguros

Data: 21 de julho de 2026.

- Runtime: registros vinculados ao schema publicado e a sua versao exata.
- Validacao: tipos, obrigatoriedade, padroes, campos desconhecidos e unicidade.
- Confiabilidade: idempotencia de criacao e concorrencia otimista de atualizacao.
- Seguranca: permissoes por operacao e mascaramento/bloqueio por campo no backend.
- Privacidade: eventos sem valores e exclusao fisica de registro e revisoes.
- Rastreabilidade: revisoes imutaveis enquanto o registro existe, auditoria e outbox.
- Migracao: `20260721_0031`.
- Proximo passo exato: validar o ciclo e criar layouts e visualizacoes para o Metadata Studio.

### Evidencia de validacao do ciclo 8

- Ruff: 246 arquivos formatados e lint aprovado.
- MyPy: 175 arquivos aprovados.
- Backend: 112 testes unitarios aprovados.
- Integracao: 10 testes aprovados.
- Seguranca: segredos, Actions, Node, Bandit e dependencias Python sem bloqueios.
- Migracao: `0031 -> 0030 -> 0031` aprovada; banco em `20260721_0031 (head)`.
- Privacidade: exclusao remove registro e revisoes; eventos nao contem valores empresariais.
- Confiabilidade: repeticao idempotente e atualizacao com versao obsoleta validadas.

## Ciclo empresarial 9 - Orkestral Metadata Studio

Data: 21 de julho de 2026.

- Navegacao: Studio permissionado e acessivel pelo menu lateral.
- Construtor: entidades e campos configuraveis sem editar codigo.
- Publicacao: validacao, publicacao e criacao de nova versao na interface.
- Runtime visual: formulario e lista gerados pelos tipos do schema publicado.
- Operacao: criacao, edicao e exclusao de registros com versao otimista.
- Experiencia: interface responsiva, em portugues e sem exposicao de JSON interno.
- Proximo passo exato: validar frontend e integrar layouts e visualizacoes salvas ao backend.

### Evidencia de validacao do ciclo 9

- ESLint: aprovado sem avisos.
- TypeScript: typecheck aprovado.
- Frontend: 12 testes aprovados em 5 arquivos.
- Build: artefato de producao gerado com `VITE_AUTH_PREVIEW_ENABLED=false`.
- E2E: 6 cenarios aprovados e 2 cenarios extensos ignorados pela configuracao local.
- Studio E2E: login, schema, validacao, publicacao, registro e exclusao aprovados.
- Seguranca: segredos, Actions, Node, Bandit e dependencias Python sem bloqueios.
- Divida tecnica: bundle principal possui aviso de 853 kB; aplicar code splitting em ciclo futuro.

## Ciclo 10 - Governança de agentes

- Versões de agentes com rascunho, publicação, aposentadoria, checksum e migração de agentes existentes.
- Níveis de autonomia 0 a 4 aplicados no back-end conforme o risco de cada ferramenta.
- Orçamento mensal por agente com reserva preventiva, limite rígido e consumo rastreável.
- Eventos e auditoria sem instruções, prompts ou credenciais.
- Testes unitários de política/checksum e integração multiempresa adicionados.
- Validação concluída: Ruff e MyPy aprovados; 119 testes unitários e 11 testes de integração aprovados; auditoria de segurança sem bloqueios; migração validada em downgrade e upgrade.
- Migração: `20260721_0032_agent_governance.py`.
- Próximo passo: ciclo 11, trace de execuções, limites de passos/tempo e modo sombra.

## Ciclo 11 - Observabilidade e modo sombra de agentes

- Trace seguro por execução, sem persistir prompt ou raciocínio interno.
- Limites de passos e tempo aplicados no back-end.
- Modos `live`, `shadow` e `simulation`, com ações externas bloqueadas fora do modo real.
- Endpoints de histórico de execuções isolados por empresa.
- Validação concluída: Ruff e MyPy aprovados; 121 testes unitários e 11 testes de integração aprovados; auditoria de segurança sem bloqueios; migração validada em downgrade e upgrade.
- Migração: `20260721_0033_agent_run_observability.py`.
- Próximo passo: ciclo 12, políticas de dados por provedor e defesa contra prompt injection.

## Ciclo 12 - Segurança de dados dos agentes

- Política de saída de dados por agente e provedor, aplicada no back-end.
- Mascaramento de PII e credenciais antes de processamento externo.
- Defesa contra prompt injection em mensagens e conhecimento recuperado.
- Incidentes auditáveis sem armazenamento do conteúdo original.
- Validação concluída: Ruff e MyPy aprovados; 123 testes unitários e 11 testes de integração aprovados; auditoria de segurança sem bloqueios; migração validada em downgrade e upgrade.
- Migração: `20260721_0034_agent_data_security.py`.
- Próximo passo: ciclo 13, suites de avaliação, casos adversariais e bloqueio de publicação.

## Ciclo 13 - Avaliação e gate de publicação de agentes

- Suítes e casos adversariais vinculados à versão do agente.
- Avaliação determinística de prompt injection e contratos de ferramentas.
- Resultados e pontuação auditáveis, sem chamada a provedor pago.
- Publicação bloqueada até aprovação quando a política exigir.
- Validação concluída: Ruff e MyPy aprovados; 124 testes unitários e 11 testes de integração aprovados; auditoria de segurança sem bloqueios; migração validada em downgrade e upgrade.
- Migração: `20260721_0035_agent_evaluation_gate.py`.
- Próximo passo: ciclo 14, contratos de tarefa e coordenação multiagente.

## Ciclo 14 - Coordenação multiagente

- Contratos entre supervisor e especialista com propagação de ferramentas, passos e custo.
- Delegações idempotentes com profundidade, prazo e máquina de estados controlada.
- Handoffs aprováveis que revalidam o agente de destino sem ampliar privilégios.
- Objetivos e resultados persistidos somente como fingerprints por empresa.
- Validação concluída: Ruff e MyPy aprovados; 126 testes unitários e 11 testes de integração aprovados; auditoria de segurança sem bloqueios; migração validada em downgrade e upgrade.
- Migração: `20260721_0036_multiagent_coordination.py`.
- Próximo passo: ciclo 15, fila assíncrona de delegações e execução coordenada.

## Ciclo 15 - Worker seguro de delegações

- Payload temporário protegido por AES-256-GCM e vinculado a empresa/delegação.
- Mensagens Redis contêm somente o identificador da delegação.
- Claim transacional, lease, retry, recuperação e expiração automática.
- Execução coordenada valida versão, política, autonomia, ferramentas, passos e custo.
- Destruição do ciphertext em qualquer estado terminal.
- Validação concluída: Ruff e MyPy aprovados; 127 testes unitários da API, 11 testes de integração e 2 testes do worker aprovados; auditoria de segurança sem bloqueios; migração validada em downgrade e upgrade.
- Migração: `20260721_0037_delegation_worker_payloads.py`.
- Próximo passo: ciclo 16, aprovação humana assíncrona em delegações de alto risco.

## Ciclo 16 - Aprovação assíncrona de delegações

- Pausa antes de ferramentas que exigem aprovação humana.
- Argumentos protegidos por AES-256-GCM e ausentes de notificações/eventos.
- Integração com a central de aprovações e retomada pela fila após commit.
- Revalidação completa antes de executar a chamada aprovada.
- Destruição de objetivo e argumentos em rejeição, expiração ou falha.
- Migração: `20260721_0038_delegation_approvals.py`.
- Contratos OpenAPI e tipos TypeScript regenerados para os ciclos empresariais acumulados.
- Validação local: Ruff e MyPy aprovados; 128 testes da API, 11 integrações,
  2 testes do worker e 12 testes do front-end aprovados; E2E com 6 aprovados e
  2 cenários explicitamente ignorados; build, migração reversível, auditoria de
  dependências e varredura de segredos aprovados.
- Próximo passo: ciclo 17, políticas de aprovação por valor e contexto.

## Ciclo 17 - Políticas empresariais de aprovação

- Regras por empresa e agente, com chave estável, versões imutáveis e publicação controlada.
- Efeitos `allow`, `require_approval` e `deny`, prioridade determinística e bloqueio seguro.
- Condições por ferramenta, faixa de valor em microunidades, moeda e contexto aninhado.
- Aprovador e prazo configuráveis, sem exposição dos argumentos em notificações ou eventos.
- Reavaliação da política imediatamente antes da execução aprovada.
- API administrativa com isolamento multiempresa, auditoria e evento transacional.
- Migração: `20260721_0039_agent_approval_policies.py`.
- Validação local: Ruff, MyPy e Prettier aprovados; 130 testes da API, 11
  integrações, 2 testes do worker e 12 testes do front-end aprovados; build,
  contratos gerados, migração reversível e auditoria de segurança aprovados.
- Próximo passo: ciclo 18, testes de isolamento da política e experiência administrativa.

## Ciclo 18 - Estúdio de políticas e validação operacional

- Painel em português dentro do agente para criar, revisar e publicar políticas.
- Configuração guiada de efeito, prioridade, ferramenta, valor, moeda e contexto.
- Simulador de decisão antes da publicação e da execução real.
- Estados visuais claros para rascunho, publicada e substituída.
- Layout responsivo e protegido pela permissão `agents.configure`.
- Defesa em profundidade descarta políticas de outra empresa ou agente mesmo
  diante de uma coleção de dados misturada.
- E2E cobrindo criação de agente, política, publicação, simulação e limpeza.
- Validação local: 131 testes da API, 11 integrações, 2 testes do worker, 12
  testes do front-end e E2E com 7 aprovados e 2 cenários explicitamente
  ignorados; MyPy, lint, Prettier, build e auditoria de segurança aprovados.
- Próximo passo: ciclo 19, aprovação por alçada e escalonamento.

## Ciclo 19 - Alçadas e escalonamento de aprovações

- Alçadas configuráveis pela prioridade, ferramenta, contexto e faixa de valor já versionadas.
- Aprovador principal e substituto validados como membros ativos com `approvals.decide`.
- Escalonamento automático antes da expiração, com reatribuição idempotente pelo worker.
- Revogação de acesso revalidada no momento do escalonamento, sem ampliar privilégios.
- Notificação dedicada, ação de auditoria e evento transacional sem argumentos empresariais.
- Interface em português para prazo, aprovador principal, substituto e simulação da decisão.
- Migração: `20260721_0040_agent_approval_escalation.py`.
- Validação local: Ruff, MyPy, ESLint, TypeScript e Prettier aprovados; 133 testes da
  API, 11 integrações, 2 testes do worker e 12 testes do front-end aprovados;
  build, migração reversível, auditoria de segurança e E2E com 7 aprovados e 2
  cenários explicitamente ignorados concluídos sem bloqueios.
- Próximo passo: ciclo 20, cadeias com múltiplos estágios e quórum de aprovação.

## Ciclo 20 - Cadeias de aprovação e quórum

- Estágios versionados e relacionais, com ordem, participantes e quórum próprios.
- Separação de funções: uma pessoa não pode ocupar mais de uma etapa da mesma cadeia.
- Votos únicos por solicitação, etapa e usuário, protegidos também por restrição no banco.
- Revalidação de empresa e approvals.decide em cada voto, inclusive após revogação.
- Aprovação parcial mantém a operação bloqueada; rejeição encerra e destrói payloads sensíveis.
- Avanço automático para a próxima etapa com notificação apenas aos novos participantes.
- Progresso de etapa e quórum visível na Central de Atenção, sem expor argumentos.
- Migração: 20260721_0041_agent_approval_quorum.py.
- Validação local: Ruff, MyPy, ESLint, TypeScript e Prettier aprovados; 133 testes da
  API, 11 integrações, 2 testes do worker e 12 testes do front-end aprovados;
  build, migração reversível, auditoria de segurança e E2E com 7 aprovados e 2
  cenários explicitamente ignorados concluídos sem bloqueios.
- Próximo passo: ciclo 21, políticas temporais, delegação formal e substituição por ausência.

## Ciclo 21 - Vigência e cobertura segura de aprovações

- Políticas versionadas agora possuem início e fim opcionais de vigência e são ignoradas fora da janela publicada.
- Cobertura formal por ausência limitada a 90 dias, restrita a aprovadores ativos da mesma empresa.
- Prevenção de autodelegação, sobreposição, ciclos e delegação em cascata no mesmo período.
- Lista de candidatos dedicada por privilégio mínimo, sem exigir acesso amplo ao cadastro de usuários.
- Voto registra o ator real e a vaga representada; titular e substituto não conseguem votar duas vezes na mesma etapa.
- Revogação é exclusiva do titular, auditada e interrompe imediatamente novas decisões representadas.
- Central de Atenção permite programar, acompanhar e revogar coberturas; Estúdio de Agentes permite configurar a vigência da política.
- Migração: `20260721_0042_approval_delegations.py`.
- Validação local: Ruff e MyPy aprovados em 189 arquivos; ESLint, TypeScript e Prettier aprovados; 135 testes da API, 12 integrações, 2 testes do worker e 12 testes do front-end aprovados; build, migração `0042 -> 0041 -> 0042`, auditoria de segurança e E2E com 7 aprovados e 2 cenários explicitamente ignorados concluídos sem bloqueios.
- Runtime local: `/health`, `/ready` e `/app` responderam `200`; banco em `20260721_0042 (head)`.
- Risco conhecido: o bundle web permanece acima de 500 kB e o `TestClient` emite aviso de depreciação do `httpx`.
- Próximo passo: ciclo 22, memória de agentes com classificação, retenção, expiração e eliminação segura por empresa.

## Ciclo 22 - Governança e eliminação de memória de agentes

- Política individual por agente com retenção padrão e máxima, escopos, classificações e consentimento obrigatório para memória pessoal.
- Conteúdo cifrado antes da persistência; respostas, eventos e auditorias contêm apenas metadados operacionais.
- Fingerprint HMAC contextualizado por empresa e agente, impedindo comparação direta entre tenants e criação duplicada.
- Memórias expiradas são excluídas das consultas ativas e podem ser eliminadas fisicamente em lote.
- Exclusão individual remove o ciphertext do banco ativo e mantém somente auditoria sem conteúdo empresarial.
- Interface em português no perfil do agente para configurar retenção, consentimento, expurgo e exclusão.
- Migração: `20260721_0043_agent_memory_governance.py`.
- Validação local: Ruff e MyPy aprovados em 193 arquivos; ESLint, TypeScript e Prettier aprovados; 136 testes da API, 12 integrações, 2 testes do worker e 12 testes do front-end aprovados; build, migração `0043 -> 0042 -> 0043`, auditoria de segurança e E2E com 7 aprovados e 2 cenários explicitamente ignorados concluídos sem bloqueios.
- Segurança comprovada: teste real confirma isolamento multiempresa, exigência de consentimento, idempotência, ausência do segredo na API e no armazenamento em texto simples, e remoção física do registro.
- Limite consciente: memórias ainda não são enviadas ao modelo; a recuperação será ligada somente após aplicar política de egress e filtragem de classificação.
- Próximo passo: ciclo 23, recuperação autorizada de memória, expurgo automático e proteção de egress por provedor.
