# Status de Implementacao Empresarial do Orkestral

Atualizado em: 21 de julho de 2026

## Fase atual

**Fase 3 - Eventos e automacoes (em andamento)**

O primeiro ciclo do Prompt Mestre concluiu os itens imediatos 1 a 3:

1. inventario inicial do repositorio;
2. confirmacao da arquitetura real;
3. execucao e estabilizacao das suites existentes.

Progresso realista da Fase 0: **100%**.

Progresso realista do roteiro empresarial completo: **35%**.

Percentuais reavaliados no ciclo 52 conforme codigo, migracoes, testes e matriz de equivalencia; nao representam apenas a quantidade de telas.

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

## Ciclo 23 - Recuperação segura e expurgo automático de memória

- Recuperação de memória desativada por padrão e limitada por agente, empresa, classificação, expiração e quantidade máxima por consulta.
- Conteúdo só é decifrado depois da autorização; memórias não autorizadas nunca entram no contexto do modelo.
- Memórias com indícios de prompt injection são bloqueadas e geram evento de segurança contendo somente fingerprint e metadados.
- Envio de memória a provedor externo exige autorização independente `allow_memory_egress`; permitir egress geral não libera memória implicitamente.
- Dados sensíveis autorizados seguem mascaramento antes de sair para um provedor externo.
- Worker elimina periodicamente ciphertexts expirados em lotes bloqueados por transação, evitando concorrência entre consumidores.
- Migração: `20260721_0044_agent_memory_runtime.py`, incluindo a origem auditável `memory` no contrato de eventos de segurança.
- Validação local: formato e Ruff aprovados nos arquivos do ciclo; MyPy aprovado em 196 arquivos; 137 testes da API, 3 testes do worker, 12 integrações e 12 testes do front-end aprovados; build e auditoria de segurança concluídos sem bloqueios; E2E com 7 aprovados e 2 cenários explicitamente ignorados.
- Migração reversível `0044 -> 0043 -> 0044` aprovada; banco em `20260721_0044 (head)`.
- Runtime local: `/health`, `/ready` e `/app` responderam `200`; PostgreSQL e Redis prontos.
- Dívida técnica preexistente: o lint global ainda alcança 28 migrações históricas com ordenação antiga de imports; nenhuma foi alterada neste ciclo para preservar o histórico Alembic.
- Riscos conhecidos: bundle web acima de 500 kB e aviso de depreciação do `TestClient`/`httpx` permanecem sem regressão.
- Próximo passo: ciclo 24, memória por usuário, revogação de consentimento e rastreabilidade de recuperação por execução.

## Ciclo 24 - Titularidade, revogação e rastreabilidade da memória

- Memórias pessoais exigem titular explícito e associação ativa à mesma empresa; memórias de outro usuário não entram no contexto do modelo.
- Banco mantém FKs independentes para usuário e associação empresarial, com exclusão em cascata quando a pessoa deixa a empresa, sem enfraquecer o contrato de `company_id`.
- Referências de consentimento deixaram de ser persistidas ou retornadas em texto; somente HMAC contextualizado por empresa, agente e titular é armazenado.
- Migração expira memórias pessoais legadas antes de remover a coluna textual, permitindo eliminação automática segura.
- Revogação é idempotente, elimina fisicamente todos os ciphertexts vinculados e bloqueia reutilização posterior da mesma autorização.
- Auditoria e evento de revogação não contêm titular, referência de consentimento nem conteúdo da memória.
- Cada memória recuperada gera `memory_access` vinculado à execução usando apenas fingerprint e metadados operacionais.
- Interface administrativa permite selecionar o titular, revogar a referência e acompanhar a quantidade eliminada sem exibir o conteúdo protegido.
- Migração: `20260721_0045_agent_memory_consent.py`.
- Validação local: Ruff e MyPy aprovados em 196 arquivos de produção; 137 testes da API, 3 do worker, 12 integrações e 12 testes do front-end aprovados; build e auditoria de segurança concluídos sem bloqueios; E2E com 7 aprovados e 2 cenários explicitamente ignorados.
- Migração reversível `0045 -> 0044 -> 0045` aprovada; banco em `20260721_0045 (head)`.
- Runtime local: `/health`, `/ready` e `/app` responderam `200`.
- Segurança comprovada: teste real impede recuperação por outro usuário da mesma empresa, remove memória ao revogar, torna a revogação repetível e bloqueia recriação com consentimento revogado.
- Próximo passo: ciclo 25, políticas de memória por escopo, limites de contexto por tokens e expiração de memória de conversa ao encerrar a sessão.

## Ciclo 25 - Políticas por escopo e ciclo de vida da conversa

- Política relacional por escopo define retenção e permissão de recuperação sem depender de JSON não validado.
- Configurações antigas permanecem compatíveis por meio de padrões seguros derivados da política principal.
- Contexto de memória possui orçamento entre 128 e 16 mil tokens estimados; conteúdos que excedem o saldo não são enviados ao modelo.
- Recuperação continua limitada por quantidade, classificação, empresa, agente, titular, expiração, escopo e política de egress.
- Conversas possuem fechamento formal e idempotente com `closed_at`; novas mensagens em conversa encerrada retornam conflito.
- Fechamento elimina fisicamente todas as memórias cujo `source_type` e `source_id` apontam para a conversa.
- Auditoria e evento de fechamento registram somente IDs operacionais e quantidade eliminada, sem conteúdo ou autoria persistente adicional.
- Interface permite configurar retenção e recuperação de cada escopo, orçamento do contexto e encerrar a conversa com retorno compreensível.
- Migração: `20260721_0046_agent_memory_lifecycle.py`.
- Validação local: Ruff e MyPy aprovados em 196 arquivos de produção; ESLint e TypeScript aprovados; 137 testes da API, 3 do worker, 12 integrações e 12 testes do front-end aprovados; build e auditoria de segurança sem bloqueios; E2E com 7 aprovados e 2 cenários explicitamente ignorados.
- Migração reversível `0046 -> 0045 -> 0046` aprovada; banco em `20260721_0046 (head)`.
- Runtime local: `/health`, `/ready` e `/app` responderam `200`.
- Risco conhecido: estimativa de tokens usa aproximação determinística e conservadora; tokenizador específico poderá ser conectado por provedor sem alterar a política.
- Próximo passo: ciclo 26, revisão e eliminação de memória pelo próprio titular, exportação segura de metadados e retenção por finalidade.

## Ciclo 26 - Direitos do titular e finalidade da memória

- Usuário com acesso ao agente pode revisar somente os metadados das próprias memórias pessoais, sem permissão administrativa.
- Eliminação self-service aplica filtros simultâneos de empresa, agente, escopo e titular e remove fisicamente o ciphertext.
- Exportação JSON contém somente metadados autorizados; conteúdo, HMAC e referência de consentimento nunca são incluídos.
- Acesso de outra empresa retorna `404` e outro usuário da mesma empresa recebe lista vazia, comprovando isolamento horizontal.
- Finalidades `service`, `personalization`, `operations`, `compliance` e `analytics` possuem políticas relacionais de habilitação e retenção.
- Retenção efetiva usa o menor valor entre política global, escopo, finalidade e solicitação, impedindo ampliação por cliente.
- Fingerprint do conteúdo passou a incluir a finalidade, evitando deduplicação indevida entre bases legais distintas.
- Interface permite configurar finalidades e oferece ao titular exportação e exclusão das próprias memórias.
- Correção visual: retorno de encerramento da conversa voltou ao card de conversa, em vez do card de ferramentas.
- Migração: `20260721_0047_agent_memory_subject_rights.py`.
- Validação local: Ruff e MyPy aprovados em 196 arquivos de produção; ESLint, TypeScript e Prettier aprovados; 137 testes da API, 3 do worker, 12 integrações e 12 testes do front-end aprovados; build e auditoria de segurança sem bloqueios; E2E com 7 aprovados e 2 cenários explicitamente ignorados.
- Migração reversível `0047 -> 0046 -> 0047` aprovada; banco em `20260721_0047 (head)`.
- Runtime local: `/health`, `/ready` e `/app` responderam `200`.
- Segurança comprovada: exportação não contém segredo, fingerprint ou consentimento; finalidade desabilitada é rejeitada; titular remove a própria memória sem alcançar dados alheios.
- Próximo passo: ciclo 27, memória de tarefa vinculada, conclusão com eliminação e política de retenção legal para exceções aprovadas.

## Ciclo 27 - memória de tarefa e retenção legal aprovada

- Memórias de escopo `task` agora exigem vínculo relacional com uma delegação ativa da mesma empresa e do agente supervisor ou executor.
- Encerramentos manuais, automáticos, por falha e por expiração eliminam a memória operacional da tarefa.
- Retenção excepcional exige solicitação registrada e aprovação de uma segunda pessoa; autoaprovação e acesso entre empresas são bloqueados.
- Referências jurídicas são armazenadas somente como HMAC, sem texto original em respostas, eventos ou auditoria.
- Memória preservada por obrigação legal deixa de ser recuperável pelo agente depois do encerramento da tarefa.
- Migração: `20260721_0048`.
- Próximo passo: memória de tarefa compartilhada entre agentes com contrato de acesso explícito, minimização de contexto e revogação.

## Ciclo 28 - compartilhamento mínimo e revogável de memória de tarefa

- Compartilhamento exige contrato explícito e idempotente, limitado à delegação e aos dois agentes que realmente participam da tarefa.
- Cada contrato declara finalidade, classificações, quantidade máxima, orçamento total de caracteres e prazo nunca superior ao vencimento da tarefa.
- A recuperação entrega somente memórias `task` da delegação exata, elimina conteúdo com indício de injeção e não expõe fingerprints ou outras memórias do agente.
- Revogação produz efeito imediato; a justificativa é preservada somente como HMAC e nunca aparece em respostas, eventos ou auditoria.
- Eventos e auditorias registram apenas identificadores, limites e contagens, sem conteúdo compartilhado.
- Migração: `20260721_0049`.
- Próximo passo: consumir o contrato diretamente no executor da delegação, registrar o uso no trace operacional e testar revogação concorrente durante a execução.

## Ciclo 29 - consumo seguro e trace de memória na delegação

- O executor usa automaticamente apenas o contrato ativo de finalidade `coordination` destinado ao agente responsável pela delegação.
- O conteúdo minimizado é protegido pela política do provedor e enviado como dados de apoio, com instrução explícita para nunca tratar o trecho como comando.
- Um checkpoint final relê o contrato depois da recuperação; revogação ou expiração durante o preparo remove todo o contexto antes da chamada ao modelo.
- Cada tentativa gera trace sem conteúdo com contrato, delegação, execução, desfecho, quantidade de itens, caracteres e bloqueios.
- Auditoria e evento operacional registram somente identificadores e contadores seguros.
- Migração: `20260721_0050`.
- Próximo passo: adicionar políticas de compartilhamento por ferramenta, limites agregados por delegação e alertas para tentativas repetidas de contexto bloqueado.

## Ciclo 30 - política por ferramenta, orçamento agregado e alertas

- Cada contrato de memória declara ferramentas autorizadas e a API rejeita chaves fora do contrato canônico da tarefa.
- A política do agente supervisor define orçamento agregado de itens e caracteres para toda a delegação, independentemente da quantidade de grants ativos.
- O executor produz trace `tool_policy_denied` ou `aggregate_limit_denied` sem recuperar conteúdo quando uma política ou limite impede o uso.
- Contextos bloqueados por injeção são contados em janela de 24 horas; ao atingir o limiar configurado, o solicitante recebe alerta seguro sem conteúdo suspeito.
- A tela de governança permite configurar os três novos limites sem expor controles internos do executor.
- Migração: `20260721_0051`.
- Próximo passo: criar política de compartilhamento por classificação de dados, aprovação humana para contexto restrito e orçamento de custo por contrato.

## Ciclo 31 - classificação, aprovação restrita e orçamento de custo

- Grants declaram teto de classificação e a API rejeita qualquer classe acima desse limite.
- Contexto `restricted` exige decisão de outra pessoa; autoaprovação é bloqueada e o executor ignora contratos pendentes ou rejeitados.
- Cada grant possui orçamento em microunidades; o executor estima o custo antes da chamada ao modelo e produz `cost_limit_denied` quando o teto seria excedido.
- Decisões, custos e desfechos são auditados sem conteúdo sensível.
- Migração: `20260721_0052`.
- Próximo passo: expiração automática de aprovações, revogação em lote por incidente e painel consolidado de riscos de memória.

## Ciclo 32 - expiração de aprovação, incidente e risco consolidado

- Aprovações para contexto restrito possuem janela de 5 a 240 minutos; após o prazo, API e executor deixam de autorizar o contexto sem depender de tarefa agendada.
- Incidentes revogam atomicamente todos os grants ativos de um agente, com idempotência, isolamento multiempresa, auditoria e evento de domínio.
- Referência e motivo do incidente são persistidos somente como fingerprints HMAC; textos operacionais não entram em banco, evento ou resposta.
- O painel do agente consolida acessos ativos, aprovações, bloqueios, incidentes e revogações em linguagem clara.
- Migração: `20260721_0053`.
- Próximo passo: criar fila de revisão de incidentes, política de quarentena temporária e exportação assinada do relatório de risco.

## Ciclo 33 - revisão independente, quarentena e relatório assinado

- Cada incidente entra em fila e somente outra pessoa da mesma empresa pode confirmá-lo ou descartá-lo; decisões cruzadas entre empresas e autorrevisão são bloqueadas.
- A abertura ativa quarentena de 5 minutos a 24 horas, impede novos grants e só é liberada pelo prazo ou por descarte independente.
- O relatório de risco é serializado de forma canônica, assinado por HMAC-SHA256 e pode ser verificado pela API; conteúdo e texto do incidente não são exportados.
- A interface exibe quarentena, revisões pendentes, fila de incidentes e download do relatório assinado.
- Migração: `20260721_0054`.
- Próximo passo: exigir quorum configurável para incidentes críticos, adicionar cadeia de custódia dos relatórios e criar exercícios automatizados de resposta.

## Ciclo 34 - quorum, cadeia de custódia e exercícios de resposta

- Revisões são votos únicos por pessoa; incidentes críticos exigem pelo menos duas pessoas e só mudam de estado quando uma decisão alcança o quorum configurado.
- Cada relatório recebe sequência e assinatura anterior, e a API valida HMAC, registro persistido e continuidade da cadeia antes de aceitá-lo como íntegro.
- Exercícios de resposta verificam quarentena, quorum crítico, isolamento multiempresa e cadeia de relatórios sem ler conteúdo protegido ou alterar dados operacionais.
- A interface permite configurar severidade/quorum, acompanhar votos e executar exercícios com resultado objetivo.
- Migração: `20260721_0055`.
- Próximo passo: adicionar SLA e escalonamento da fila, rotação de chaves com verificação histórica e agendamento recorrente de exercícios.

## Ciclo 35 - SLA, rotação de assinatura e agenda de exercícios

- Incidentes possuem SLA configurável de 5 minutos a 24 horas, prazo explícito e indicação objetiva de atraso na API e na interface.
- Escalonamento em lote processa somente revisões vencidas ainda não escalonadas, com repetição segura, auditoria e evento sem texto sensível.
- Relatórios usam chaves derivadas por versão; a rotação cria uma nova versão sem persistir material secreto e preserva a verificação histórica enquanto o segredo mestre permanecer disponível.
- A cadeia de custódia registra a versão usada em cada assinatura e rejeita divergência entre o relatório apresentado e o registro persistido.
- Exercícios de resposta possuem agenda persistente, intervalo controlado e executor de vencimento que registra a próxima execução sem fingir execução antecipada.
- A interface permite acompanhar SLAs, escalonar atrasos, rotacionar assinaturas, configurar a agenda e executar exercícios vencidos.
- Migração: `20260721_0056_agent_memory_sla_key_schedule.py`.
- Próximo passo: entregar notificações para responsáveis pelo incidente, keyring para rotação segura do segredo mestre e disparo da agenda pelo worker.

## Ciclo 36 - alertas, keyring mestre e execução recorrente

- Incidentes novos notificam revisores independentes autorizados; SLA vencido produz alerta crítico separado e idempotente, sem referência ou motivo sensível.
- Memórias antigas passam a ser lidas pelo keyring `ENCRYPTION_PREVIOUS_KEYS`, enquanto toda nova gravação continua usando exclusivamente `ENCRYPTION_KEY`.
- Versões de assinatura registram somente um identificador não secreto da chave mestre e selecionam a chave histórica correta durante a verificação.
- Troca da chave ativa cria nova versão automaticamente; ausência da chave histórica falha de forma segura e compreensível.
- Celery Beat busca agendas vencidas a cada cinco minutos; bloqueio `SKIP LOCKED` impede processamento duplicado entre workers concorrentes.
- Exercícios agendados usam o mesmo avaliador dos exercícios manuais, geram auditoria/evento e notificam o responsável quando algum controle falha.
- Migração: `20260721_0057_agent_memory_keyring.py`.
- Próximo passo: recriptografia controlada de memórias com checkpoint, destinatários responsáveis explícitos por incidente e métricas operacionais do scheduler.

## Ciclo 37 - recriptografia, responsáveis e métricas do scheduler

- Incidentes passam a registrar responsáveis independentes em tabela relacional, com validação de empresa, autorização e separação entre abertura e revisão.
- Notificações novas e atrasadas são enviadas somente aos responsáveis explícitos; incidentes legados mantêm fallback para a fila autorizada.
- Revisões por pessoas não atribuídas são bloqueadas no back-end, sem depender de ocultação de botões na interface.
- A rotação do segredo mestre possui job persistente por agente, lote configurável, checkpoint ordenado, progresso, falha segura e exclusão mútua por empresa/agente.
- O worker recriptografa somente com o keyring ativo, nunca persiste material secreto e interrompe o job se a chave-alvo mudar ou um ciphertext não puder ser aberto.
- Conclusões produzem auditoria, evento e notificação sem conteúdo de memória; a chave anterior só pode ser removida depois da verificação operacional documentada.
- Exercícios registram origem e duração; a API consolida aprovações, falhas, média de duração, última execução e atraso do scheduler.
- A interface permite selecionar responsáveis, acompanhar telemetria do worker e iniciar/monitorar a recriptografia em linguagem clara.
- Migração: `20260721_0058_agent_memory_reencryption_ownership_metrics.py`.
- Validação local: Ruff e MyPy aprovados em 197 arquivos de produção; ESLint, TypeScript e Prettier aprovados; 142 testes da API/worker, 12 integrações e 12 testes do front-end aprovados; build e auditoria de segurança sem bloqueios.
- Migração reversível `0058 -> 0057 -> 0058` aprovada; banco em `20260721_0058 (head)`.
- Runtime local: `/health`, `/ready` e `/app` responderam `200`; E2E com 7 cenários aprovados e 2 explicitamente ignorados.
- Segurança comprovada: outra empresa recebe `404`, responsável não atribuído é bloqueado, ciphertext permanece legível somente com a chave ativa depois da recriptografia e nenhum segredo é exposto por API, auditoria ou evento.
- Próximo passo: retomada operacional de jobs falhos, reatribuição auditada de responsáveis e alerta automático de heartbeat/SLO do scheduler.

## Ciclo 38 - retomada, reatribuição e SLO operacional

- Jobs de recriptografia registram o último item existente no momento da solicitação; memórias novas, já protegidas pela chave ativa, ficam fora do snapshot e não alteram o total durante a execução.
- Um job falho pode ser retomado somente por pessoa autorizada, com keyring histórico disponível, justificativa protegida por HMAC e continuidade no checkpoint confirmado.
- A retomada zera somente a tentativa falha, preserva a quantidade já recriptografada e atualiza a chave-alvo sem persistir material secreto.
- Incidentes pendentes permitem reatribuição explícita para revisores autorizados da mesma empresa; autorrevisão e usuários externos continuam bloqueados.
- Pessoas que já votaram não podem ser removidas da cadeia de custódia, e a justificativa da mudança nunca é armazenada em texto puro.
- O contrato idempotente do incidente mantém uma impressão digital HMAC imutável da solicitação original, permitindo replay seguro mesmo depois da reatribuição sem aceitar colisões de payload.
- A agenda registra heartbeat do worker, SLO de 5 minutos a 24 horas, último alerta e quantidade de violações.
- Ao retornar depois de uma indisponibilidade acima do SLO, o worker emite notificação crítica e evento seguro; a API diferencia heartbeat aguardando, saudável, vencido ou desativado.
- A interface oferece retomada do checkpoint, reatribuição com justificativa e leitura operacional do heartbeat.
- Migração: `20260721_0059_agent_memory_recovery_ownership_slo.py`.
- Validação local: Ruff e MyPy aprovados em 197 arquivos de produção; ESLint, TypeScript e Prettier aprovados; 142 testes da API/worker, 13 integrações e 12 testes do front-end aprovados; build e auditoria de segurança concluídos sem vulnerabilidades conhecidas.
- Migração reversível `0059 -> 0058 -> 0059` aprovada; banco em `20260721_0059 (head)`.
- Runtime local: `/health`, `/ready` e `/app` responderam `200`; worker saudável; E2E com 7 cenários aprovados e 2 explicitamente ignorados.
- Segurança comprovada: falhas de recriptografia respeitam os invariantes do banco, retomadas preservam o checkpoint, reatribuições continuam isoladas por empresa e justificativas são persistidas somente por HMAC.
- Risco operacional preexistente: o container n8n responde ao contrato E2E, mas seu health check interno retorna `503`; investigar separadamente sem enfraquecer o readiness obrigatório da API.
- Próximo passo: monitor externo do heartbeat, política de tentativas máximas e runbook assistido de recuperação de chave.

## Ciclo 39 - monitor externo, orçamento de retry e recuperação assistida

- Probe público `GET /health/agent-memory-scheduler` permite que um monitor independente detecte heartbeat vencido por HTTP `503` sem revelar tenant, agente ou métricas internas.
- Script portátil consulta o probe com timeout e código de saída próprio para integração com qualquer monitor, sem acoplamento a provedor.
- Jobs definem de uma a dez retomadas; API, interface e restrição do banco impedem ultrapassar o orçamento persistido.
- Toda retomada exige diagnóstico recente que verifica keyring, identificação da chave, snapshot, concorrência e orçamento sem expor segredos.
- Avaliações geram auditoria e evento de domínio; aprovação expira em 15 minutos e é consumida pela retomada.
- Interface apresenta diagnóstico e instruções operacionais antes de liberar o botão de checkpoint.
- Migração: `20260721_0060_agent_memory_monitor_retry_recovery.py`.
- Validação local: Ruff e MyPy aprovados em 197 arquivos; 143 testes da API/worker, 13 integrações e 12 testes do front-end aprovados; ESLint, TypeScript, Prettier, build e auditoria de segurança sem bloqueios.
- Migração reversível `0060 -> 0059 -> 0060` aprovada; banco em `20260721_0060 (head)`.
- Runtime local: Nginx validado e recarregado; `/health`, `/ready`, `/app` e o probe externo responderam `200`; worker saudável; E2E com 7 aprovados e 2 explicitamente ignorados.
- Segurança comprovada: probe sem dados de tenant, acesso cruzado ao diagnóstico retorna `404`, retry sem avaliação ou acima do orçamento retorna `409` e nenhum segredo aparece na resposta assistida.
- Próximo passo: monitoramento autenticado por ambiente, cofre externo com rotação coordenada e política de encerramento definitivo de jobs irrecuperáveis.

## Ciclo 40 - autenticação do monitor, cofre externo e encerramento terminal

- O probe do scheduler exige assinatura HMAC-SHA256 com timestamp de curta duração; segredos ausentes, assinaturas inválidas e replay fora da janela falham de forma fechada.
- O script de monitoramento calcula a assinatura a partir do ambiente do processo, sem enviar o segredo em argumento de linha de comando.
- Produção exige provedor de chaves externo; referências ativas e históricas são coordenadas com o keyring e persistidas nos jobs somente por impressão digital SHA-256.
- O diagnóstico de recuperação verifica também provedor e referência antes de liberar uma retomada.
- Jobs bloqueados ou sem orçamento podem ser encerrados definitivamente com código técnico, usuário, horário, auditoria, evento e notificação; a justificativa nunca é armazenada nem retornada em texto.
- Jobs encerrados não podem ser retomados e continuam isolados por empresa.
- Migração: `20260721_0061_agent_memory_monitor_auth_vault_terminal.py`.
- Validação local: Ruff e MyPy aprovados em 198 arquivos; 139 testes da API, 5 do worker, 12 integrações e 12 testes do front-end aprovados; ESLint, TypeScript, Prettier, build e auditoria sem vulnerabilidades conhecidas.
- Migração reversível `0061 -> 0060 -> 0061` aprovada; banco em `20260721_0061 (head)`.
- Runtime local: `/health`, `/ready`, `/app` e monitor HMAC responderam `200`; API, worker e gateway saudáveis; E2E com 7 aprovados e 2 explicitamente ignorados.
- Segurança comprovada: acesso sem assinatura ou com timestamp expirado retorna `401`, fechamento cruzado retorna `404`, job encerrado não pode ser retomado e justificativas não aparecem nas respostas.
- Risco operacional preexistente: o container n8n responde ao contrato E2E, mas seu health check interno permanece em `503`; investigar separadamente sem reduzir as proteções do gateway.
- Próximo passo: gestão de referências de cofre por credencial vinculada, rotação automatizada do segredo do monitor e política de retenção dos registros terminais.

## Ciclo 41 - credencial de cofre, rotação do monitor e retenção terminal

- Jobs com provedor externo exigem credencial criptografada ativa da mesma empresa contendo `key_reference`; a API nunca retorna seu ID, URI ou conteúdo.
- O diagnóstico bloqueia credenciais revogadas, expiradas, externas ao tenant ou diferentes do vínculo HMAC original.
- O monitor aceita o segredo ativo e uma lista temporária de segredos anteriores únicos, permitindo rotação sem indisponibilidade e remoção após a janela antirreplay.
- Jobs terminais recebem prazo configurável entre 7 e 3.650 dias; o worker remove registros vencidos e preserva auditoria agregada sem identificadores operacionais.
- A interface informa apenas se há credencial vinculada e a data limite de retenção.
- Migração: `20260721_0062_agent_memory_vault_monitor_retention.py`.
- Validação local: Ruff e MyPy aprovados em 198 arquivos; 140 testes da API, 5 do worker, 12 integrações e 12 testes do front-end aprovados; ESLint, TypeScript, Prettier, build e auditoria sem vulnerabilidades conhecidas.
- Migração reversível `0062 -> 0061 -> 0062` aprovada; banco em `20260721_0062 (head)`.
- Runtime local: `/health`, `/ready`, `/app` e monitor HMAC responderam `200`; API, worker e gateway saudáveis; E2E com 7 aprovados e 2 explicitamente ignorados.
- Segurança comprovada: credencial ausente retorna `409`, vínculo de outro tenant retorna `404`, vínculo válido não expõe ID e registro terminal vencido é removido com auditoria agregada.
- Risco operacional preexistente: o container n8n responde ao contrato E2E, mas seu health check interno permanece em `503`; investigar separadamente sem reduzir as proteções do gateway.
- Próximo passo: seleção guiada de credenciais por catálogo, rotação programada do segredo do monitor e legal hold específico para jobs de recriptografia.

## Ciclo 42 - catálogo de cofre, prazo de rotação e legal hold

- A API lista somente credenciais ativas da empresa atual que declaram `key_reference`; a interface substitui o UUID manual por seleção guiada com nome e plugin.
- Ambientes remotos exigem data de rotação do segredo do monitor e recusam inicialização quando a idade máxima configurada é excedida.
- Jobs terminais aceitam retenção legal com referência protegida por HMAC, motivo tipado, prazo e separação obrigatória entre solicitante e decisor.
- Holds pendentes ou aprovados bloqueiam o expurgo; após expirar, a política normal de retenção volta a remover o registro operacional.
- Catálogo, criação, decisão e expurgo permanecem filtrados por empresa, sem revelar credenciais nem referências jurídicas de outro tenant.
- Migração: `20260721_0063_agent_memory_vault_catalog_hold.py`.
- Validação local: Ruff e MyPy aprovados em 197 arquivos de produção; 142 testes da API, 5 do worker, 13 integrações e 12 testes do front-end aprovados; ESLint, TypeScript, Prettier, build e auditoria sem vulnerabilidades conhecidas.
- Migração reversível `0063 -> 0062 -> 0063` aprovada; banco em `20260721_0063 (head)`.
- Runtime local: ambiente iniciado pelo script oficial; `/health`, `/ready`, `/app` e monitor HMAC responderam `200`; API, worker e gateway saudáveis; E2E com 7 aprovados e 2 explicitamente ignorados.
- Segurança comprovada: catálogo não lista credenciais de outro tenant, autoaprovação retorna `409`, decisão cruzada retorna `404`, referência jurídica não aparece na resposta e hold ativo bloqueia o expurgo.
- Risco operacional preexistente: o container n8n responde ao contrato E2E, mas seu health check interno permanece em `503`; investigar separadamente sem reduzir as proteções do gateway.
- Próximo passo: alertas prévios de vencimento de segredo, notificações do legal hold e conectores nativos para cofres gerenciados.

## Ciclo 43 - alertas de rotação, notificações e cofres gerenciados

- O probe HMAC informa estado de rotação `healthy`, `due_soon` ou `not_configured`; o script externo emite aviso antes do prazo configurado sem expor datas ou segredos.
- Solicitações de retenção legal notificam revisores independentes autorizados da empresa e decisões notificam o solicitante, sem transportar a referência jurídica.
- O catálogo reconhece credenciais gerenciadas e apresenta o provedor na interface, preservando compatibilidade com conectores personalizados.
- AWS Secrets Manager, Azure Key Vault, Google Secret Manager e HashiCorp Vault possuem contratos nativos, referências com esquema próprio e bloqueio de segredo embutido na URI.
- Testes de conexão desses cofres não simulam sucesso: validam o contrato local e informam claramente quando a leitura remota não foi executada.
- Migração: `20260721_0064_managed_vault_connectors.py`.
- Validação local concluída: Ruff nos 232 arquivos não históricos e na migração nova; MyPy em 193 arquivos; API `148 passed`; worker `5 passed`; integração multiempresa `13 passed`; web `12 passed`; E2E `7 passed` e `2 skipped`; ESLint, TypeScript, Prettier, build e auditoria de segurança aprovados; migração `0064 -> 0063 -> 0064`; `/health`, `/ready`, `/app` e monitor HMAC validados.
- Dívida anterior não alterada: 24 avisos Ruff de ordenação de imports em migrações históricas e em `app/scripts/migrate.py`; nenhum pertence aos arquivos deste ciclo.
- Próximo passo: resolução real por identidade gerenciada, lembretes de hold próximos do vencimento e política de rotação por ambiente.

## Ciclo 44 - identidade gerenciada, lembretes e rotação por ambiente

- Implementada resolução real de segredos via identidade da carga de trabalho para AWS Secrets Manager, Azure Key Vault, Google Secret Manager e HashiCorp Vault, sem credenciais estáticas nos conectores e sem exposição do material resolvido.
- As referências são analisadas por contrato estrito; metadados, redirecionamentos, tamanho de resposta, travessia de caminho e mensagens de erro possuem limites defensivos.
- O teste de conexão de cofre agora somente retorna sucesso após leitura remota válida; falhas do provedor são sanitizadas.
- Retenções legais de jobs de recriptografia recebem lembrete idempotente antes do vencimento, com auditoria, evento de domínio e notificações limitadas à empresa e sem referência jurídica.
- A API informa se o lembrete já foi enviado, e o worker executa a manutenção junto ao ciclo de recriptografia.
- A política de rotação do monitor é específica por ambiente: `optional` local, `warn` desenvolvimento e `enforce` produção/desenvolvimento remoto.
- Migração: `20260721_0065_reencryption_hold_reminders.py`.
- Validação local concluída: Ruff em 234 arquivos e na migração nova; MyPy em 194 arquivos; API `156 passed`; worker `5 passed`; integração multiempresa `13 passed`; web `12 passed`; E2E `7 passed` e `2 skipped`; ESLint, TypeScript, Prettier, build e auditoria de segurança aprovados; migração `0065 -> 0064 -> 0065`; `/health`, `/ready`, `/app` e monitor HMAC validados.
- Dívida anterior não alterada: 24 avisos Ruff de ordenação de imports em migrações históricas e em `app/scripts/migrate.py`; nenhum pertence aos arquivos deste ciclo.
- Próximo passo: ativação segura de keyrings externos na criptografia de memória, lembretes renováveis com nova aprovação e métricas operacionais por provedor de cofre.

## Ciclo 45 - keyring externo ativo e métricas de cofres

- Criado vínculo de keyring gerenciado por empresa e agente, ativado somente após recriptografia concluída e protegido por credencial ativa, provedor e impressão da referência.
- Leituras autorizadas, memória compartilhada e novas gravações resolvem o keyring do agente pela identidade da carga; falhas fecham o acesso e retornam mensagens seguras.
- A chave externa é primária e as chaves de ambiente permanecem somente como fallback transitório de migração. O teste comprova que a chave de ambiente isolada não descriptografa uma nova memória gerenciada.
- Adicionada rota de status do keyring sem IDs de credencial nem referências e com ocultação `404` entre empresas.
- Adicionado resumo operacional por provedor de cofre com total, sucessos, falhas, taxa, latência média e último teste, sempre filtrado por `company_id`.
- Migração: `20260721_0066_agent_memory_external_keyrings.py`.
- Validação local concluída: Ruff em 234 arquivos e na migração nova; MyPy em 194 arquivos; API `156 passed`; worker `5 passed`; integração multiempresa `13 passed`; web `12 passed`; E2E `7 passed` e `2 skipped`; ESLint, TypeScript, Prettier, build e auditoria de segurança aprovados; migração `0066 -> 0065 -> 0066`; `/health`, `/ready`, `/app` e monitor HMAC validados.
- Dívida anterior não alterada: 24 avisos Ruff de ordenação de imports em migrações históricas e em `app/scripts/migrate.py`; nenhum pertence aos arquivos deste ciclo.
- Próximo passo: renovação de retenções com nova aprovação, recriptografia de saída antes da revogação do keyring e painel visual das métricas por provedor.

## Ciclo 46 - renovação legal, saída segura e painel de cofres

- Criado histórico de renovações de retenção legal com extensão limitada, nova referência protegida e decisão independente por solicitação.
- Aprovações ampliam a retenção e rearmam o lembrete; rejeições preservam o prazo anterior. Toda decisão gera auditoria, evento e notificação sem referência jurídica.
- Implementada recriptografia de saída: a chave de ambiente volta a ser primária, o keyring externo é usado apenas para leitura transitória e o vínculo só é revogado após conclusão.
- O teste comprova ida para chave externa, impossibilidade de abertura pela chave de ambiente isolada, retorno para ambiente e leitura posterior pela chave local.
- A tela de agentes exibe status do keyring e métricas por provedor com atualização periódica, linguagem operacional e sem credenciais.
- Migração: `20260721_0067_reencryption_hold_renewals.py`.
- Validação local concluída: Ruff em 234 arquivos e na migração nova; MyPy em 194 arquivos; API `156 passed`; worker `5 passed`; integração multiempresa `13 passed`; web `12 passed`; E2E `7 passed` e `2 skipped`; ESLint, TypeScript, Prettier, build e auditoria de segurança aprovados; migração `0067 -> 0066 -> 0067`; `/health`, `/ready`, `/app` e monitor HMAC validados.
- Dívida anterior não alterada: 24 avisos Ruff de ordenação de imports em migrações históricas e em `app/scripts/migrate.py`; nenhum pertence aos arquivos deste ciclo.
- Próximo passo: renovação e saída disponíveis na interface, alertas de indisponibilidade do cofre e política de expiração/revogação automática de credenciais vinculadas.

## Ciclo 47 - interface de governança e ciclo de vida do cofre

- A tela de agentes permite solicitar renovação de retenção legal, decidir extensões pendentes e iniciar a saída segura de um keyring gerenciado sem alterar a configuração global do ambiente.
- O worker monitora cada vínculo ativo por identidade da carga, abre incidentes idempotentes, alerta responsáveis após o limiar e registra a recuperação sem persistir a mensagem do provedor.
- Credenciais próximas do vencimento iniciam automaticamente a recriptografia para a chave do ambiente; a revogação ocorre somente depois que nenhum vínculo ativo depende delas.
- Status e incidentes são filtrados por `company_id`, e a API não retorna IDs de credencial, referências de chave ou material resolvido.
- Migração: `20260721_0068_memory_vault_lifecycle.py`.
- Validação local concluída: Ruff e MyPy aprovados em 198 arquivos; API `156 passed`; worker `5 passed`; integração multiempresa `13 passed`; web `12 passed`; E2E `7 passed` e `2 skipped`; ESLint, TypeScript, Prettier, build e auditoria de segurança aprovados; migração `0068 -> 0067 -> 0068`; `/health`, `/ready`, `/app` e monitor HMAC validados.
- O teste de integração foi isolado do worker contínuo para impedir consumo concorrente das delegações sintéticas; o worker foi religado e permaneceu saudável.
- Próximo passo: políticas configuráveis por empresa, renovação de credenciais antes da saída e SLO operacional dos cofres gerenciados.

## Ciclo 48 - política empresarial, renovação de credencial e SLO

- Política de keyring configurável por empresa define aviso de vencimento, saída automática, lote, limiar de falhas e SLO sem alterar padrões de outros tenants.
- Credenciais vinculadas e ainda válidas recebem renovação governada por aprovação independente; justificativas são reduzidas a HMAC e não retornam pela API.
- Saída segura iniciada, credencial vencida, autoaprovação, decisão repetida e acesso entre empresas são bloqueados no back-end.
- Incidentes rompendo o SLO geram escalonamento idempotente com notificação, auditoria e evento; status e histórico aparecem na interface sem segredos.
- Migração: `20260721_0069_memory_vault_policy_renewal_slo.py`.
- Validação local concluída: Ruff e MyPy aprovados em 198 arquivos; API `156 passed`; worker `5 passed`; integração multiempresa `13 passed`; web `12 passed`; E2E `7 passed` e `2 skipped`; ESLint, TypeScript, Prettier, build e auditoria de segurança aprovados.
- Migração reversível `0069 -> 0068 -> 0069` aprovada; banco em `20260721_0069 (head)`; `/health`, `/ready`, `/app` e o probe HMAC do worker responderam corretamente com API, worker e gateway saudáveis.
- A dependência transitiva vulnerável `js-yaml 4.2.0` foi substituída por `4.3.0` via override central do workspace; as auditorias Node e Python não encontraram vulnerabilidades conhecidas.
- Risco operacional anterior não alterado: o health check interno do n8n permanece em `unhealthy`, embora o contrato E2E de disponibilidade continue aprovado.
- Próximo passo: escalonamento por plantão, histórico de disponibilidade e rotação coordenada da identidade da carga.

## Ciclo 49 - plantão, disponibilidade e rotação da identidade

- A política do cofre aceita plantonistas ativos da própria empresa e inclui essa equipe nos alertas operacionais, sem permitir IDs duplicados ou de outro tenant.
- O monitor mantém janelas horárias agregadas por empresa e provedor com sucessos, falhas, violações de SLO e disponibilidade percentual por sete a noventa dias de consulta.
- A identidade da carga possui rotação cifrada e governada: solicitação, aprovação independente, teste real de acesso ao cofre, ativação atômica, auditoria, evento e notificação.
- Identidade atual, identidade proposta e justificativa nunca são retornadas; autoaprovação, acesso cruzado, credencial inválida e rotação durante saída segura são bloqueados.
- A tela de agentes permite escolher o plantão, acompanhar disponibilidade e solicitar/decidir rotações sem revelar dados do cofre.
- Migração: `20260721_0070_vault_oncall_availability_identity.py`.
- Validação local concluída: Ruff e MyPy aprovados em 198 arquivos; API `156 passed`; worker `5 passed`; integração multiempresa `13 passed`; web `12 passed`; E2E `7 passed` e `2 skipped`; ESLint, TypeScript, Prettier, build e auditoria de segurança aprovados.
- Migração reversível `0070 -> 0069 -> 0070` aprovada; banco em `20260721_0070 (head)`; contratos idempotentes e `/health`, `/ready`, `/app` e probe HMAC do worker aprovados.
- Segurança comprovada: plantonista de outro tenant retorna `422`, autoaprovação retorna `409`, decisão cruzada retorna `404`, a identidade proposta é validada no cofre e nenhum texto de identidade ou justificativa aparece na API.
- Risco operacional anterior não alterado: o health check interno do n8n permanece em `unhealthy`, embora o contrato E2E de disponibilidade continue aprovado.
- Próximo passo: retenção do histórico, escala de plantão com horários e teste canário automatizado da identidade antes do vencimento.

## Ciclo 50 - retenção, janela de plantão e canário preventivo

- A política empresarial controla retenção de disponibilidade, fuso e janela diária do plantão, antecedência do canário e intervalo entre verificações.
- A manutenção remove agregados vencidos por tenant e mantém janelas atuais, sem tocar em incidentes, auditoria ou dados criptográficos.
- O canário testa a identidade real antes do vencimento da credencial, alerta de forma idempotente na falha e registra a recuperação sem armazenar erro ou referência do provedor.
- A interface mostra política, janela e estado do último canário; fusos inválidos e horários incoerentes são recusados pelo contrato da API.
- Migração: `20260721_0071_vault_retention_oncall_canary.py`.
- Validação local concluída: Ruff e MyPy aprovados em 198 arquivos; API `174 passed`; worker `5 passed`; integração multiempresa `13 passed`; web `12 passed`; E2E `7 passed` e `2 skipped`; ESLint, TypeScript, Prettier, build e auditoria de segurança aprovados.
- Migração reversível `0071 -> 0070 -> 0071` aprovada; banco em `20260721_0071 (head)`; contratos regenerados e probe HMAC do worker aprovado.
- Segurança comprovada: fusos e janelas inválidos são recusados, a retenção é aplicada por tenant, o canário usa a identidade real sem persistir referência ou erro do provedor e alertas de falha/recuperação são idempotentes.
- Próximo passo: escalas semanais por plantonista, exportação de SLO e canário com promoção gradual da identidade.

## Ciclo 52 - layouts, visualizacoes e regras por metadados

- Layouts e secoes pertencem a uma versao exata da entidade e controlam a ordem do formulario no Orkestral Studio.
- Visualizacoes definem colunas, filtros e ordenacao por contrato validado, com uma visualizacao padrao por versao.
- Regras usam somente operadores deterministas permitidos e sao aplicadas pela API ao criar ou atualizar registros.
- Configuracoes publicadas sao imutaveis; a nova versao copia o design anterior e exige nova validacao antes da publicacao.
- Alteracoes geram Policy Decision, auditoria sem valores empresariais e evento transacional por empresa.
- Migracao: `20260721_0072_metadata_layout_view_rules.py`.
- Proximo passo: relacionamentos tipados, formulas seguras e tipos de registro com layouts condicionais.

## Evidências finais do ciclo 52

- Plataforma de metadados validada de ponta a ponta com layouts versionados, visualizações configuráveis e regras determinísticas aplicadas também no back-end.
- Migrações `20260721_0072` e `20260721_0073` aplicadas; a `0073` teve downgrade e upgrade executados com sucesso e passou a preservar notificações operacionais de severidade crítica.
- Testes da API: 158 aprovados; testes do worker: 5 aprovados.
- Testes de integração: 13 aprovados com o worker assíncrono isolado durante a suíte e restaurado ao final.
- Testes do front-end: lint, tipos, 12 testes e build aprovados.
- Testes E2E: 7 aprovados e 2 ignorados por contrato do ambiente; nenhum cenário falhou.
- Segurança: isolamento entre empresas, regras no servidor, alerta crítico, auditoria, análise de segredos e dependências permaneceram aprovados.
- Próximo recorte exato: relacionamentos tipados, fórmulas seguras e tipos de registro com layouts condicionais.

## Ciclo 53 - acesso seguro de sócios somente leitura

- Link temporário com token aleatório armazenado somente como hash.
- Autenticação administrativa obrigatória, limitada e com autorização curta de uso único.
- Seleção restrita a usuários das empresas administradas e expiração configurável.
- Sessão `Administrador Somente Leitura` com empresa fixa, interface administrativa e bloqueio universal de escrita no backend.
- Auditoria de criação, uso e tentativas mutáveis bloqueadas.
- Migração `20260721_0074`, integração de ponta a ponta e documentação operacional.

## Ciclo 54 - relacionamentos, formulas e tipos de registro

- Relacionamentos UUID tipados e isolados por empresa validam o registro de destino e impedem exclusao enquanto houver referencia ativa.
- Formulas declarativas calculam campos no servidor com operadores permitidos, deteccao de ciclos, limite de operandos e bloqueio de escrita manual.
- Tipos de registro versionados selecionam layouts condicionais e acompanham o registro e seu historico de revisoes.
- O Orkestral Studio configura e opera os tres recursos sem expor JSON ou codigo executavel ao usuario.
- Migracao `20260721_0075`, contratos OpenAPI, testes multiempresa e documentacao correspondentes.

## Ciclo 55 - visualizacoes, filtros, paginacao e pacotes portateis

- multiplas visualizacoes configuraveis e selecionaveis no Studio;
- filtros e ordenacao persistidos, validados por tipo e executados no backend;
- paginacao real dos registros personalizados;
- exportacao e importacao de schema sem dados de clientes ou identificadores de tenant;
- checksum de integridade, auditoria e eventos de importacao/exportacao;
- testes unitarios e integrados entre duas empresas.

Proximo recorte: versionamento formal de pacotes, dependencias, dry-run de instalacao e promocao
controlada de metadados entre ambientes.

## Ciclo 56 - ciclo de vida de pacotes de metadados

- catalogo multiempresa de pacotes e versoes SemVer;
- snapshots imutaveis com checksum do manifesto e artefato;
- dependencias exatas obrigatorias ou opcionais;
- previa vinculante antes de qualquer instalacao;
- registro de instalacoes por empresa e ambiente;
- promocao controlada com bundle verificavel entre ambientes adjacentes;
- painel de releases e instalacao no Orkestral Studio;
- proximo recorte: permissoes de entidade, campo e acao para metadados e compartilhamento de registros.

## Ciclo 57 - seguranca fina da plataforma de metadados

- Registros personalizados agora possuem proprietario e escopo `all`, `owned` ou `owned_shared`.
- Regras por usuario ou papel controlam acoes da entidade; regra direta do usuario prevalece.
- Regras de campo controlam leitura e edicao no backend, com mascaramento e resposta `403`.
- Compartilhamentos concedem leitura ou edicao a usuarios e papeis sem permitir exclusao.
- Configuracao visual entregue no Studio de Metadados, incluindo revogacao de compartilhamento.
- Auditoria e outbox registram configuracao, compartilhamento e revogacao sem valores empresariais.
- Migracao: `20260721_0077_metadata_permissions_sharing.py`.
- Testes do recorte cobrem propriedade, campo restrito, compartilhamento e isolamento entre empresas.
- Proximo recorte: iniciar a Fase 3 com contratos versionados de eventos, transactional outbox e consumidores idempotentes para automacoes.

## Ciclo 58 - Fase 3: contratos e consumidores de eventos (21/07/2026)

- **Concluido no codigo:** contratos versionados, assinaturas, entregas persistentes, consumo idempotente, retentativas, DLQ, replay auditado, workflow por evento e central operacional.
- **Migracao:** `20260721_0078_event_contracts_consumers.py`.
- **Seguranca:** permissoes `events.view`, `events.configure` e `events.replay`; isolamento por `company_id`; payload nao exposto na central; replay sem mutacao do original.
- **Testes adicionados:** validacao/compatibilidade de contrato, consumo unico, DLQ, replay e acesso cruzado.
- **Documento detalhado:** `docs/cycles/CYCLE_58_EVENT_CONTRACTS_AND_CONSUMERS.md`.
- **Proximo passo exato:** gatilhos canonicos de evento no construtor visual, simulacao e observabilidade de automacoes.

## Ciclo 59 - gatilhos de evento e simulacao de automacoes (22/07/2026)

- Gatilho `trigger.domain_event` integrado ao modelo canonico e aos contratos publicados.
- Assinaturas de workflow sincronizadas automaticamente na publicacao e desativacao.
- Politicas de etapas, timeout e concorrencia validadas e aplicadas no backend.
- Simulacao sem efeitos externos com validacao de payload e trace seguro.
- Estudio visual com configuracao do evento, limites e resultado passo a passo.
- Migracao: nenhuma; utiliza o schema de eventos do ciclo 58.
- Proximo passo exato: cancelamento cooperativo, compensacao declarativa e metricas agregadas por automacao.

## Ciclo 60 - controle e metricas de automacoes (22/07/2026)

- Cancelamento cooperativo com estado, solicitante, motivo e auditoria.
- Compensacao manual declarativa para falha ou cancelamento, sem reversao automatica.
- Metricas agregadas de sucesso, erro, latencia, cancelamento e replay.
- Painel operacional e acoes supervisionadas no Estudio de Automacoes.
- Migracao: `20260722_0079_workflow_execution_control.py`.
- Proximo passo exato: retry por bloco, circuit breaker de provider e cancelamento remoto por adaptador.

## Ciclo 61 - resiliencia de automacoes (22/07/2026)

- Retry configuravel e limitado por bloco no contrato canonico.
- Circuit breaker persistente por empresa e provider, compartilhado entre processos.
- Saude do circuito visivel sem expor configuracoes internas.
- Capacidade de cancelamento remoto declarada pelo adaptador sem usar API privada.
- Migracao: `20260722_0080_workflow_provider_resilience.py`.
- Proximo passo exato: compensacao vinculada a blocos, provider fake e fechamento da Fase 3.

## Ciclo 62 - protecao de acesso e ambiente (22/07/2026)

- Rate limit distribuido separado entre API e autenticacao, com falha fechada nas rotas sensiveis.
- Login protegido simultaneamente por conta e IP; recuperacao de senha limitada sem enumeracao de usuarios.
- Identificadores Redis protegidos por HMAC e IP de proxy aceito somente quando explicitamente confiavel.
- Ambientes remotos recusam placeholders, segredos centrais reutilizados e protecoes criticas desativadas.
- Nginx sobrescreve cabecalhos de encaminhamento, limita rajadas/conexoes e oculta a versao.
- Testes adicionados para configuracao remota, proxy confiavel, politica especifica, resposta `429` e falha fechada.
- Migracao: nenhuma.
- Documento detalhado: `docs/cycles/CYCLE_62_ACCESS_AND_ENV_SECURITY.md`.
- Proximo passo exato do plano mestre permanece: compensacao vinculada a blocos, provider fake e fechamento da Fase 3.

## Ciclo 63 - deploy manual e estabilizacao (22/07/2026)

- Auto-Deploy do Render desligado no contrato; push e merge nao publicam a aplicacao.
- Workflow de desenvolvimento restrito a inicio manual com SHA completo.
- Script manual valida branch, SHA, endpoint do hook e versao publicada sem expor o segredo.
- Contratos CI/CD impedem a reintroducao de gatilho automatico.
- Circuit breaker inicializa estado e contador no dominio, independentemente do flush do banco.
- Teste do monitor isolado de PostgreSQL externo ao processo de teste.
- Migracao: nenhuma.
- Documento detalhado: `docs/cycles/CYCLE_63_MANUAL_DEPLOY_AND_STABILIZATION.md`.
- Proximo passo exato: compensacao vinculada a blocos, provider fake e fechamento da Fase 3.

## Ciclo 64 - compensacao por bloco e portabilidade do provider (22/07/2026)

- A definicao canonica vincula cada acao operacional a um bloco compensatorio exclusivo e fora do caminho normal.
- Falhas e cancelamentos persistem um plano seguro; cada item exige confirmacao humana e auditoria propria.
- `WorkflowProvider` centraliza sincronizacao, ativacao, execucao, health e cancelamento remoto.
- O adaptador n8n preserva compatibilidade e referencias legadas durante a migracao.
- O provider falso prova publicacao, execucao, cancelamento e ausencia de dependencia do formato n8n.
- Referencias genericas e provider usado em cada execucao permitem futura troca de motor sem reescrever o dominio.
- Correcao adicional: a validacao de risco de repeticao nao consulta mais uma variavel de loop durante a validacao de eventos.
- Migracao: `20260722_0081_workflow_provider_compensation.py`.
- Documento detalhado: `docs/cycles/CYCLE_64_WORKFLOW_PORTABILITY_AND_COMPENSATION.md`.
- Fase 3 concluida. Proximo passo exato: iniciar a Fase 4 com definicoes e versoes do runtime de agentes, ferramentas tipadas e politicas de autonomia.

## Ciclo 65 — Trace operacional seguro de agentes

- Fase atual: Fase 4, runtime empresarial de agentes.
- Concluído: `agent_run_steps`, API isolada por empresa, fingerprints HMAC, instrumentação de chat, simulação e delegações, painel responsivo e migração reversível `20260722_0082`.
- Segurança: nenhum prompt, argumento, resultado completo, segredo ou raciocínio interno é persistido no trace.
- Testes concluídos: 193 API, 5 worker, 13 front-end, 19 integrações, 7 E2E aprovados e 2 E2E condicionais ignorados; build, tipagem, migração reversível, auditoria de segurança e contratos CI/CD/remotos aprovados.
- Próximo passo exato: agenda e gatilhos versionados por agente, com vínculo seguro de credenciais e enforcement no worker.

## Atualização — Ciclo 66: agendas, gatilhos e credenciais de agentes

- Fase atual: Fase 4 — Runtime de agentes.
- Concluído: agendas e gatilhos versionados, publicação/pausa, vínculos seguros ferramenta-credencial, dispatcher idempotente, auditoria, eventos e painel administrativo.
- Migração: `20260722_0083_agent_schedules_credentials.py`.
- Segurança: isolamento por `company_id`, permissões no backend, validação de ferramenta e credencial, nenhuma exposição de segredo e bloqueio seguro da fila.
- Próximo passo exato: consumir despachos `ready` pelo executor governado, aplicando política, orçamento, aprovação, modo sombra/canary e trace antes de qualquer ferramenta real.
### Evidencias finais do ciclo 66

- `20260722_0083` confirmado no head do Alembic.
- 197 testes da API, 6 do worker, 19 de integracao, 13 da interface e 7 E2E aprovados.
- Oito servicos locais saudaveis; health e readiness aprovados.
- Rate limit independente para login automatico local, sem reduzir a protecao remota.
- Proximo passo: consumir despachos prontos pelo executor governado, aplicando politica,
  orcamento, aprovacao, modo sombra e rastreabilidade antes de chamar ferramentas reais.
## Ciclo 67 - Em desenvolvimento

- executor duravel para despachos prontos;
- pre-validacao de tenant, versao, responsavel, ferramenta, argumentos e permissao;
- reserva de orcamento e liberacao segura;
- modo sombra por padrao e rollout canario deterministico;
- aprovacao humana sincronizada com despacho e `AgentRun`;
- trilha operacional sem argumentos ou resultados em texto aberto;
- proximo passo: migracao, contratos, testes completos, PR e deploy manual.

### Ciclo 67 - executor governado de despachos concluido

- agendas e eventos agora alimentam um executor governado com isolamento por empresa, permissao do ator, politica publicada, autonomia, orcamento, modo sombra, canary e aprovacao humana;
- execucoes geram `AgentRun`, trace operacional, auditoria e eventos sem armazenar objetivos ou resultados sensiveis em texto livre;
- ferramentas internas nao sensiveis dispensam credenciais externas; ferramentas sensiveis permanecem fail-closed;
- validacao: API `207 passed`, integracao `20 passed`, worker `6 passed`, E2E `7 passed / 2 skipped`, auditoria de seguranca aprovada;
- proximo passo exato: controles visuais para modo sombra/canary e reconciliacao fail-closed de despachos interrompidos.

## Atualizacao - Ciclo 68

**Fase atual:** runtime empresarial de agentes, reconciliacao e controles de
despacho.

**Concluido:**

- reconciliacao fail-closed de despachos interrompidos;
- liberacao idempotente da reserva de custo;
- bloqueio de repeticao automatica para ferramentas externas;
- trace, auditoria e evento de dominio de interrupcao;
- controles de modo sombra, execucao real e canario;
- argumentos JSON validados por ferramenta;
- visualizacao dos estados completos da fila;
- testes unitarios, de interface e de integracao do recorte.

**Migracoes:** nenhuma; o ciclo utiliza contratos persistidos existentes.

**Risco residual:** uma repeticao deliberada ainda precisa de uma operacao
administrativa dedicada, com nova aprovacao e idempotencia explicita.

**Proximo passo exato:** implementar a central administrativa de revisao de
despachos interrompidos, com decisao auditada de encerrar ou preparar nova
execucao.

## Atualizacao - Ciclo 69

**Fase atual:** runtime empresarial de agentes, revisao humana de interrupcoes.

**Concluido:**

- decisao imutavel de encerrar ou preparar repeticao;
- aprovacao explicita com permissao `agents.execute`;
- idempotencia independente para solicitacao e aprovacao;
- nova linhagem persistida por `retry_of_dispatch_id`;
- revalidacao de credenciais antes da nova fila;
- auditoria e eventos confidenciais;
- isolamento multiempresa com resposta 404;
- central de revisao dentro da fila segura;
- migracao Alembic `20260722_0085`;
- teste de integracao ponta a ponta e testes de interface.

**Risco residual:** faltam indicadores operacionais e alertas para revisoes
pendentes por tempo excessivo.

**Proximo passo exato:** implementar metricas e alertas de SLA da fila de revisao,
com agregacao por empresa e sem armazenar argumentos de ferramentas.

## Atualizacao - Ciclo 70

**Fase atual:** observabilidade operacional do runtime de agentes.

**Concluido:**

- resumo de SLA por empresa e agente;
- contagem de pendencias, atrasos, decisoes e reincidencias;
- alerta idempotente sem payload sensivel;
- job Celery a cada cinco minutos;
- notificacao para responsaveis autorizados;
- painel com atualizacao periodica;
- teste de atraso real, idempotencia e isolamento;
- nenhuma migracao adicional neste ciclo.

**Risco residual:** o SLA ainda e padrao e nao possui politica versionada por
empresa, agente ou risco.

**Proximo passo exato:** criar politicas versionadas de SLA e escalonamento, com
limites, auditoria e configuracao administrativa.

## Atualizacao - Ciclo 71

**Fase atual:** governanca operacional do runtime empresarial de agentes.

**Concluido:**

- politicas de SLA versionadas por empresa e agente;
- publicacao atomica com aposentadoria da versao anterior;
- limites fortes no schema e no banco;
- SLA e escalonamento efetivos no resumo e no worker;
- alertas idempotentes de aviso e escalonamento critico;
- configuracao administrativa responsiva;
- auditoria de criacao e publicacao;
- teste de isolamento multiempresa e uso da politica publicada;
- migracao Alembic `20260722_0086`.

**Validacao:** 208 testes da API, 7 do worker, 20 de integracao e 19 da
interface aprovados; 7 E2E aprovados e 2 condicionais ignorados; build,
tipagem, lint, contratos CI/CD e remoto, health checks e auditoria de seguranca
aprovados.

**Proximo passo exato:** adicionar destinatarios e escalas de plantao versionados,
com confirmacao de recebimento e reatribuicao auditada.

## Atualizacao - Ciclo 72

**Fase atual:** governanca e continuidade operacional do runtime de agentes.

**Concluido:**

- plantao ordenado e versionado por empresa e agente;
- fuso e janela de atendimento validados;
- validacao de aprovadores ativos do mesmo tenant;
- atribuicao automatica e fallback seguro;
- confirmacao idempotente pelo responsavel;
- reatribuicao manual autorizada e rotacao automatica por falta de confirmacao;
- historico encadeado e somente uma atribuicao ativa;
- auditoria, eventos e notificacoes minimizados;
- configuracao e operacao responsivas na interface;
- migracao Alembic `20260722_0087` reversivel.

**Validacao:** 208 testes da API, 7 do worker, 20 de integracao e 19 da
interface aprovados; 7 E2E aprovados e 2 condicionais ignorados; build,
tipagem, lint, contratos, health checks e auditoria de seguranca aprovados.

**Proximo passo exato:** adicionar calendario semanal, excecoes de ausencia e
passagem de plantao com aceite do substituto.

## Atualizacao - Ciclo 73

**Fase atual:** governanca e continuidade operacional do runtime de agentes.

**Concluido:**

- dias semanais versionados na politica de SLA;
- janela de plantao aplicada no fuso configurado;
- ausencias temporarias com cancelamento auditado;
- passagem de plantao idempotente entre aprovadores do mesmo tenant;
- aceite ou rejeicao exclusivo pelo substituto;
- substituicao ativa somente depois do aceite;
- expiracao segura de passagens vencidas;
- roteamento sem usuarios ausentes e com escala deduplicada;
- historico, auditoria, eventos e interface administrativa responsiva;
- migracao Alembic `20260722_0088` reversivel.

**Validacao:** 208 testes da API, 7 do worker, 20 de integracao e 19 da
interface aprovados; 7 E2E aprovados e 2 condicionais ignorados; build,
tipagem produtiva, lint, contratos, auditoria de seguranca e migracao reversivel
aprovados. O worker foi restaurado saudavel depois da integracao.

**Divida tecnica observada:** a verificacao opcional de tipagem que inclui os
testes aponta 20 anotacoes antigas em quatro arquivos; os 223 arquivos
produtivos permanecem sem erros de tipagem.

**Proximo passo exato:** adicionar multiplos turnos semanais e calendarios de
feriados, com validacao de sobreposicao e cobertura minima antes da publicacao.

## Atualizacao - Ciclo 74

**Fase atual:** fundacao de seguranca empresarial aplicada transversalmente.

**Concluido:**

- papeis PostgreSQL separados para runtime e somente leitura;
- RLS forcado em todas as tabelas com `company_id`;
- associacoes CRM e RBAC protegidas pelo tenant do pai;
- contexto de tenant transacional reaplicado depois de commit e rollback;
- bloqueio de leitura e escrita cruzada diretamente no banco;
- testes ofensivos controlados de IDOR, mass assignment, SQL injection e
  cabecalho de empresa forjado;
- contrato contra campos sensiveis em respostas da API;
- allowlist de variaveis publicas do Vite;
- proibicao de tokens persistentes no armazenamento do navegador;
- sonda sintetica de segredo e varredura do bundle compilado;
- migracao Alembic `20260722_0089` reversivel.

**Risco residual:** migracoes e workers ainda compartilham a credencial
administrativa do banco; a proxima evolucao de seguranca deve separar esses
papeis de login e seus privilegios.

**Validacao:** 216 testes de API e worker, integracoes completas com duas novas
sondas ofensivas, 19 testes de interface e 7 jornadas E2E aprovados; 2 E2E
condicionais ignorados. Build, lint, tipagem de 224 arquivos, auditoria de
dependencias/segredos e downgrade/upgrade controlado da migracao foram
aprovados. Os oito servicos locais voltaram saudaveis.

**Proximo passo exato:** separar credenciais PostgreSQL de migracao, API e
worker e, em seguida, retomar multiplos turnos e calendarios de feriados.

## Atualizacao - Ciclo 75

**Fase atual:** fundacao de seguranca empresarial aplicada transversalmente.

**Concluido:**

- contrato de identidades PostgreSQL separadas para migracao, API e worker;
- selecao explicita da conexao conforme o processo;
- homologacao e producao com validacao fail-closed obrigatoria;
- bloqueio de usuarios repetidos e contas administrativas no runtime;
- TLS validado em todas as conexoes remotas;
- erros Pydantic sem exibicao dos valores sensiveis recebidos;
- fallback legado restrito a local e desenvolvimento remoto reduzido;
- contrato CI contra segredos de infraestrutura no bundle do navegador;
- sonda RLS contra tentativa de desativar `row_security`;
- bootstrap de nova empresa com troca de tenant posterior a autorizacao;
- documentacao operacional para ativacao e rotacao sem registrar credenciais.

**Risco residual:** o ambiente gratuito remoto continua usando a credencial
legada ate que tres usuarios sejam provisionados no painel do PostgreSQL. O
codigo impede promover homologacao ou producao nesse estado.

**Validacao:** 242 testes de API, worker, integracao e seguranca aprovados; 19
testes de interface aprovados; build produtivo, lint e tipagem de 223 arquivos
aprovados. A auditoria nao encontrou segredos conhecidos nem vulnerabilidades
conhecidas nas dependencias e aprovou as sondas de RLS e fronteira do navegador.

**Proximo passo exato:** provisionar as identidades protegidas no provedor e,
depois, retomar multiplos turnos semanais e calendarios de feriados.

## Atualizacao - Ciclo 76

**Fase atual:** fechamento da governanca operacional do runtime de agentes.

**Concluido:**

- multiplos turnos semanais por plantonista;
- calendario versionado de feriados;
- cobertura minima simultanea configuravel;
- deteccao de sobreposicao por usuario e dia;
- diagnostico horario de lacunas;
- publicacao recusada pelo backend quando a escala e insegura;
- roteamento conforme o turno ativo e o feriado;
- compatibilidade com politicas legadas;
- interface responsiva de montagem e validacao;
- migracao Alembic `20260723_0090` reversivel.

**Validacao:** 242 testes de API, worker, integracao e seguranca e 19 testes da
interface aprovados; build, lint, tipagem produtiva, auditoria de
segredos/dependencias e downgrade/upgrade da migracao aprovados. Os oito
servicos locais terminaram saudaveis.

**Proximo passo exato:** iniciar a Fase 5 com identidade canonica, fontes,
qualidade, consentimento e visao 360 do cliente.

## Atualizacao - Ciclo 77

**Fase atual:** plataforma de dados e visao 360.

**Concluido:**

- perfil canonico ligado ao CRM existente;
- identidades protegidas por hash e exibicao mascarada;
- resolucao deterministica sem fusao autonoma;
- fontes e modos de obtencao dos dados;
- pontuacao e pendencias de qualidade;
- consentimentos historicos por finalidade e canal;
- oportunidades e atividades agregadas;
- API e painel responsivo de visao 360;
- auditoria, eventos e RLS nas novas tabelas;
- migracao Alembic `20260723_0091` reversivel.

**Proximo passo exato:** regras versionadas de correspondencia, fila de fusao e
desfusao humana e linhagem por atributo.

### Ciclo 77 - identidade canonica e visao 360

- Entregue: perfil canonico por empresa, identidades mascaradas, qualidade de dados, fontes e historico de consentimento.
- Seguranca: RLS forcado nas novas tabelas, isolamento entre empresas testado e valores de identidade armazenados como fingerprint.
- Validacao: 242 testes Python, 19 testes web, build, Ruff, mypy, rollback/upgrade 0091 e auditoria de seguranca aprovados.
- Proximo passo exato: regras versionadas de correspondencia, fila humana de fusao/desfusao e linhagem por campo.
### Ciclo 78 - correspondencia e governanca de identidade

- Implementado: regras versionadas, analise explicavel, fila humana e fusao reversivel.
- Implementado: linhagem por campo com fonte, classificacao e SHA-256.
- Seguranca: RLS forcado, autorizacao de backend, justificativa e trilha imutavel.
- Proximo passo exato: ingestao em lote e incremental, qualidade configuravel e dead-letter queue.

### Validacao do Ciclo 78

- Resultado: 246 testes Python, 19 testes web, build, Ruff, mypy e auditoria aprovados.
- Sonda transacional: fusao e reversao reais executadas no PostgreSQL e totalmente revertidas.
- Migracao: rollback/upgrade 0092 aprovado e RLS validado nas novas tabelas.
### Ciclo 79 - ingestao e qualidade

- Implementado: jobs idempotentes em lote e incrementais.
- Implementado: regras de qualidade versionadas e publicaveis.
- Implementado: fila de erros sem carga bruta e reprocessamento auditado.
- Seguranca: RLS forcado e fingerprints para carga, identidades e linhagem.
- Proximo passo exato: conectores agendados, cursores e observabilidade de sincronizacao.

### Validacao do Ciclo 79

- Resultado: 250 testes Python, 19 testes web, build, Ruff, mypy e auditoria aprovados.
- Sonda transacional: idempotencia e reprocessamento executados no PostgreSQL e revertidos.
- Migracao: rollback/upgrade 0093 aprovado e RLS validado.

### Ciclo 80 - sincronizacao agendada e observabilidade

- Implementado: conectores por empresa com fonte canonica e agenda persistente.
- Implementado: lease exclusivo, cursor protegido, idempotencia e backoff exponencial.
- Implementado: execucao real integrada a ingestao, pausa, retomada e metricas seguras.
- Seguranca: nenhuma credencial, token de lease, cursor bruto ou carga retorna pela API.
- Migracao: `20260723_0094` com RLS forcado e rollback.
- Validacao: 253 testes Python, 19 testes web, build, Ruff, mypy, sonda
  transacional, auditoria de seguranca e oito servicos locais aprovados.
- Proximo passo exato: registro de adaptadores, scheduler no worker e health por provedor.

### Ciclo 81 - adaptadores, scheduler e health

- Implementado: catalogo tipado de adaptadores e capacidades por transporte.
- Implementado: prontidao baseada em credencial ativa e teste de conexao.
- Implementado: scheduler idempotente e fila sem carga de cliente.
- Seguranca: descoberta global minima e processamento sob RLS por empresa.
- Migracao: `20260723_0095` reversivel.
- Proximo passo exato: executor HTTP seguro, mapeamento tipado e DLQ do adaptador.

## Atualizacao - ciclo 81: adaptadores, agendamento e saude das sincronizacoes

Situacao: concluido e validado localmente em 23 de julho de 2026.

- Catalogo tipado para `secure_push`, `generic_rest_pull` e `signed_webhook`.
- Verificacao de prontidao fechada por padrao, sem expor credenciais ou cursores.
- Agendador multiempresa com selecao segura de empresas, contexto RLS por transacao e identificador de worker armazenado como hash.
- Fila de despacho auditavel; o sistema nao declara que uma integracao externa foi executada antes do processamento real.
- Interface de configuracao e verificacao de saude disponivel em `Sincronizar dados`.
- Migracao: `20260723_0095`.
- Validacao: 257 testes, 19 testes web, build web, Ruff, mypy em 237 arquivos e auditoria de seguranca aprovados.
- Proximo passo exato: executor HTTP seguro para o adaptador REST, com protecao SSRF, claim atomico, retry, dead-letter queue e confirmacao real de resultado.
## Atualizacao - ciclo 82: execucao REST segura e fila de falhas

Situacao: concluido e validado localmente em 23 de julho de 2026.

- Execucao HTTPS real com DNS e socket presos a enderecos publicos validados.
- Bloqueio de SSRF, DNS rebinding, redirecionamento, compressao e respostas sem limite.
- Claim atomico, expiracao, retentativa, backoff e `dead_letter`.
- Credenciais descriptografadas somente no worker e nunca devolvidas ao frontend.
- Reenvio administrativo auditado e observabilidade baseada apenas em metadados seguros.
- Migracao: `20260723_0096`.
- Validacao: 269 testes, 19 testes web, build Vite, Ruff, mypy em 240
  arquivos e auditoria de seguranca aprovados.
- Migracao validada em upgrade, downgrade para `0095` e novo upgrade para `0096`.
- Proximo passo: ingestao incremental, checkpoints e Change Data Capture governado.
# Atualizacao 2026-07-23 - Ciclo 83

- fase atual: Fase 5, plataforma de dados;
- concluido neste recorte: CDC de clientes, sequencia por empresa, assinaturas,
  checkpoints monotônicos, pausa e retomada, API protegida e painel administrativo;
- privacidade: eventos nao armazenam nem retornam payload bruto;
- migracao: `20260723_0097`;
- testes novos: contratos de metadados e deduplicacao de operacoes;
- proximo passo exato: retencao segura pelo menor checkpoint, resolucao de
  identidade e fusao assistida;
- documento tecnico:
  `docs/implementation/CYCLE_83_CUSTOMER_CDC_CHECKPOINTS.md`.
# Atualizacao 2026-07-23 - Ciclo 84

- fase atual: Fase 5, plataforma de dados;
- concluido neste recorte: preview e expurgo seguro do CDC por menor checkpoint,
  maior retencao, lote limitado e bloqueio transacional;
- privacidade: nenhum payload bruto e preservado no registro da limpeza;
- migracao: `20260723_0098`;
- proximo passo exato: automatizar a manutencao e acrescentar qualidade,
  consentimento e linhagem ao perfil 360;
- documento tecnico:
  `docs/implementation/CYCLE_84_CUSTOMER_CDC_SAFE_RETENTION.md`.
# Atualizacao 2026-07-23 - Ciclo 85

- fase atual: Fase 5, plataforma de dados;
- concluido neste recorte: manutencao horaria da retencao CDC pelo worker,
  descoberta minima por funcao segura e isolamento de falhas por empresa;
- migracao: `20260723_0099`;
- seguranca: o executor automatico nao assume identidade humana e continua sob
  contexto RLS;
- proximo passo exato: qualidade e consentimento do perfil 360, com politicas
  de minimizacao e atendimento de solicitacoes LGPD;
- documento tecnico:
  `docs/implementation/CYCLE_85_CUSTOMER_CDC_RETENTION_WORKER.md`.
# Atualizacao 2026-07-23 - Ciclo 86

- fase atual: Fase 5, plataforma de dados;
- concluido neste recorte: solicitacoes de anonimização e exclusao, verificacao,
  decisao, retencao legal e execucao irreversivel;
- migracao: `20260723_0100`;
- seguranca: RLS, hashes por empresa, lock transacional e permissao de exclusao
  exigida no backend;
- proximo passo exato: exportacao segura do titular, correcao e restricao de
  processamento com pacote temporario criptografado;
- documento tecnico:
  `docs/implementation/CYCLE_86_CUSTOMER_PRIVACY_REQUESTS.md`.

## Ciclo 87 — direitos do titular e restrição de processamento

- Fase atual: 5 — Plataforma de dados.
- Concluído: exportação portátil sem cache, correção canônica, restrição/liberação de processamento, auditoria sem PII e painel administrativo.
- Migração: `20260723_0101` com RLS forçada em restrições e operações de direitos.
- Segurança: permissão `crm.contacts.export`, lock por tenant/perfil e bloqueio de ingestão para perfis restritos.
- Próximo passo: concluir ativação governada de segmentos e busca da plataforma de dados antes de iniciar a Fase 6.

## Ciclo 88 — segmentos, ativação e busca

- Fase atual: 5 — Plataforma de dados.
- Concluído: segmentos tipados/versionados, materialização, busca segura e ativação em campanhas com consentimento.
- Migração: `20260723_0102` com RLS forçada em segmentos, membros e ativações.
- Segurança: perfis restritos sempre excluídos; busca não expõe identidade bruta; ativação sem webhook externo.
- Próximo passo: validar o ciclo e encerrar a Fase 5; iniciar Fase 6 com fundação comercial empresarial.
# Atualização - Ciclo 89

- Fase atual: 6 - Vendas empresariais.
- Fundação de contas e leads implementada.
- Qualificação e conversão idempotente reutilizam CRM, perfil 360 e pipeline.
- RLS forçada, permissões granulares, auditoria e eventos sem PII bruta.
- Migração: `20260723_0103`.
- Próximo passo: produtos, tabelas de preços, propostas e inteligência comercial.
