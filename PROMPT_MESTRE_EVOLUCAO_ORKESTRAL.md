# PROMPT MESTRE - EVOLUCAO DO ORKESTRAL PARA UMA PLATAFORMA EMPRESARIAL NO NIVEL DA SALESFORCE

## Missao

Evoluir o Orkestral diretamente neste repositorio como uma plataforma SaaS empresarial completa, modular, extensivel, multiempresa e orientada por agentes de inteligencia artificial. O objetivo e alcancar equivalencia funcional com os principais problemas empresariais resolvidos pela Salesforce e superar a referencia em simplicidade, flexibilidade, transparencia, integracao, autonomia controlada e custo operacional.

O Orkestral deve ser uma implementacao propria, original e tecnicamente independente. Nao copiar codigo proprietario, identidade visual, icones, textos, marcas, componentes protegidos, estrutura visual identica ao Lightning ou documentacao proprietaria. Nomes de produtos concorrentes so podem aparecer em documentos internos de analise comparativa.

## 1. Contexto atual a confirmar no repositorio

O contexto inicial esperado inclui React, TypeScript, Vite, React Router, TanStack Query, FastAPI, SQLAlchemy assincrono, Alembic, Pydantic, PostgreSQL, Redis, Celery, n8n interno, Docker, Docker Compose, Nginx, armazenamento de objetos, GitHub e GitHub Actions.

Estrutura esperada:

- `apps/api`;
- `apps/web`;
- `apps/worker`;
- `packages`;
- `infrastructure`;
- `docs`;
- `tests`.

Recursos existentes ou planejados incluem identidade, empresas, usuarios, papeis, permissoes, modulos, plugins, CRM, suporte, projetos, marketing, estoque, financeiro, recursos humanos, analytics, automacoes, agentes, conhecimento, integracoes, billing, notificacoes, auditoria, aprovacao humana, publicacao e versionamento de fluxos, credenciais criptografadas e catalogo de plugins.

O sistema usa `Company` e `company_id`. A separacao entre empresas deve ser absoluta. Nenhuma operacao pode consultar, alterar ou compartilhar registros, memoria, credenciais, documentos, eventos, logs, arquivos ou metricas de outra empresa sem autorizacao explicita.

## 2. Regras inegociaveis de execucao

Antes de desenvolver:

1. Executar `git status`.
2. Analisar a arvore do repositorio.
3. Ler a documentacao relevante.
4. Ler Dockerfiles e arquivos Compose.
5. Ler configuracoes FastAPI.
6. Ler modelos SQLAlchemy.
7. Ler migracoes Alembic.
8. Ler servicos, repositorios e rotas existentes.
9. Ler autenticacao e permissoes.
10. Ler agentes, automacoes, plugins e integracoes.
11. Identificar os padroes do front-end.
12. Executar os testes disponiveis.
13. Separar erros anteriores de regressao causada pela mudanca.
14. Registrar o estado inicial.

Nunca executar comandos destrutivos, apagar funcionalidades, reconstruir o produto do zero ou remover dados/volumes sem autorizacao. Toda mudanca de banco deve possuir migracao Alembic segura, revisavel e preferencialmente reversivel. Manter compatibilidade das APIs ou aplicar estrategia formal de versao e migracao.

Trabalhar incrementalmente e sem interromper o ciclo para pedir autorizacao apos cada pequena entrega.

## 3. Pesquisa oficial da referencia

Antes de definir a arquitetura final, pesquisar documentacao oficial e atualizada da Salesforce, priorizando Salesforce Architects, Salesforce Developers, Salesforce Help, Trailhead, paginas oficiais dos produtos, APIs, seguranca, Agentforce, Data 360, MuleSoft, automacoes, eventos, metadados, desenvolvimento e empacotamento.

Analisar pelo menos:

- multi-tenancy e plataforma orientada por metadados;
- objetos, campos, relacionamentos, record types, layouts, formularios, validacoes e formulas;
- fluxos, aprovacoes, seguranca de objeto, campo e registro, papeis, permission sets e compartilhamento;
- auditoria, eventos, assincronicidade, APIs e integracao;
- CRM, vendas, atendimento, marketing, comercio, dados, analytics, portais e colaboracao;
- marketplace, agentes, ferramentas, seguranca, testes e observabilidade de IA;
- ciclo de vida, DevOps, sandboxes, pacotes, versoes e solucoes por setor.

Registrar data e fontes oficiais. A comparacao e um documento vivo.

## 4. Matriz de equivalencia funcional

Manter `docs/SALESFORCE_ORKESTRAL_EQUIVALENCE_MATRIX.md` com, para cada capacidade:

- capacidade de referencia;
- problema empresarial;
- usuarios;
- comportamento;
- dependencias;
- equivalente atual;
- maturidade;
- lacunas;
- solucao original Orkestral;
- modelos, endpoints, eventos, telas e permissoes;
- automacoes e agentes;
- riscos, prioridade e complexidade;
- criterios de aceitacao;
- fase e situacao.

Niveis:

- Nivel 0 - inexistente;
- Nivel 1 - prototipo;
- Nivel 2 - basico funcional;
- Nivel 3 - equivalente essencial;
- Nivel 4 - equivalente empresarial;
- Nivel 5 - superior a referencia.

Uma capacidade so pode ser concluida com codigo, migracao, testes, interface e documentacao compativeis com seu escopo.

## 5. Visao do produto

O Orkestral deve se tornar um sistema operacional empresarial orientado por agentes, reunindo sistema de registro, plataforma de aplicacoes, CRM, atendimento, marketing, comercio, financeiro, estoque, projetos, RH, dados, analytics, automacao, integracao, agentes, marketplace, portais, seguranca, governanca, desenvolvimento e observabilidade.

Usuarios devem usar modulos prontos e criar novos processos sem alterar o nucleo.

## 6. Diferenciais obrigatorios

### 6.1 Simplicidade

- interface clara e menos confusa;
- configuracao guiada;
- linguagem simples;
- modelos por setor;
- operacoes importantes em poucos passos.

### 6.2 Brasil e internacionalizacao

- portugues por padrao;
- i18n completa;
- moeda, idioma, data e fuso por empresa;
- CPF, CNPJ, Pix, boleto, NF-e e NFS-e por modulos/adaptadores;
- LGPD e extensibilidade internacional;
- nenhuma regra brasileira acoplada ao nucleo.

### 6.3 Independencia tecnologica

Nao acoplar agentes a um modelo, automacoes ao formato do n8n, arquivos a um provedor, e-mail a um servico, pagamentos a um gateway ou eventos a um broker.

### 6.4 Implantacao

Preparar SaaS publico, nuvem privada, instalacao dedicada, ambiente hibrido e futura instalacao local empresarial.

### 6.5 Custos transparentes

Mostrar por empresa uso de IA, tokens, custo estimado, execucoes, armazenamento, automacoes, integracoes, limites, excedentes e orcamentos por agente, equipe e departamento.

### 6.6 IA em todo o sistema

A IA deve interpretar, sugerir, executar tarefas autorizadas, preencher registros, atender, qualificar, criar campanhas, acompanhar estoque, detectar riscos, organizar projetos, analisar financas, conversar por canais, agendar, chamar APIs, pedir aprovacao e colaborar com outros agentes.

## 7. Plataforma orientada por metadados

Permitir por configuracao:

- aplicacoes, modulos, entidades e objetos personalizados;
- campos, tipos, relacionamentos e tipos de registro;
- formularios, secoes, abas, layouts, visualizacoes, filtros e listas;
- acoes, botoes, validacoes, formulas, padroes e campos calculados;
- estados, processos, permissoes, automacoes, gatilhos, relatorios e dashboards.

Estruturas candidatas: `ApplicationDefinition`, `ModuleDefinition`, `EntityDefinition`, `FieldDefinition`, `RelationshipDefinition`, `RecordTypeDefinition`, `LayoutDefinition`, `LayoutSection`, `ViewDefinition`, `ActionDefinition`, `ValidationRule`, `FormulaDefinition`, `AutomationBinding`, `PermissionDefinition`, `PackageDefinition`, `PackageVersion` e `TenantConfiguration`, adaptadas ao padrao existente.

Requisitos:

- definicoes globais ou por empresa;
- nucleo global imutavel para tenants;
- sobrescritas somente quando autorizadas;
- schemas versionados e validacao forte;
- rascunho, validacao, publicacao e rollback;
- front-end e back-end usando os mesmos contratos;
- seguranca por objeto, campo, registro e acao;
- busca, CRUD, eventos, importacao, exportacao e historico.

Nao usar JSON dinamico sem schema e validacao.

## 8. Modelo unificado de cliente e dados

Unificar sem misturar empresas: pessoas, contatos, contas, fornecedores, leads, oportunidades, compras, pedidos, tickets, conversas, campanhas, atividades, documentos, contratos, eventos, comportamento, preferencias, consentimentos e identidades externas.

Incluir resolucao de identidade, matching, duplicidade, fusao assistida, registro principal, fontes, qualidade, historico, linhagem, consentimento, classificacao, retencao, anonimizacao e exclusao.

Suportar dados estruturados e nao estruturados, PostgreSQL transacional, busca textual, object storage, vetores por `pgvector` quando aprovado, ingestao em lote/incremental, eventos, CDC, sincronizacao bidirecional, DLQ e reprocessamento.

Nao prometer zero-copy sem federacao real; registrar quando dados forem copiados, cacheados ou consultados na origem.

## 9. CRM e vendas empresarial

Evoluir para leads, contas, contatos, organizacoes, oportunidades, pipelines, etapas, atividades, tarefas, reunioes, chamadas, e-mails, produtos, catalogos, precos, propostas, cotacoes, descontos, contratos, pedidos, metas, territorios, equipes, divisao de receita, previsao, renovacao, upsell, cross-sell, parceiros e historico.

Adicionar progressivamente scoring, probabilidade, saude, estagnacao, proxima acao, forecast, analise de conversas, resumo, captura de atividades, alerta de risco, priorizacao, preparacao de reunioes e agentes comerciais.

Toda previsao deve mostrar dados, data, confianca, explicacao, limitacoes e revisao humana.

## 10. Atendimento empresarial

Incluir casos, tickets, filas, prioridades, categorias, tipos, estados, SLA, marcos, escalonamento, atribuicao, habilidades, carga, disponibilidade, omnichannel, e-mail, chat, WhatsApp, formulario, portal, voz por adaptador, conhecimento, respostas, macros, historico, satisfacao, CSAT, relatorios e campo.

Roteamento deve considerar empresa, canal, equipe, habilidade, idioma, prioridade, disponibilidade, carga, horario, SLA, cliente, regiao e problema.

Agentes devem identificar intencao, consultar dados autorizados, responder com base em fontes, abrir/atualizar ticket, classificar, resumir, encaminhar, executar procedimentos e transferir para humano. Nunca indicar falsamente que uma acao ocorreu.

## 11. Marketing empresarial

Incluir campanhas, publicos, segmentos, listas, jornadas, e-mail, WhatsApp, SMS, notificacoes, formularios, landing pages, conteudo, calendario, nutricao, scoring, personalizacao, consentimento, A/B, atribuicao, custos, conversoes, ROI, abandono e fidelizacao.

Jornadas devem suportar evento, segmento, manual, espera, condicao, split, A/B, envio, atualizacao, API, agente, saida, meta, limite, consentimento, horario, frequencia, versao, teste, publicacao, pausa e retomada.

Conteudo de IA deve ser identificado internamente e manter historico de revisao.

## 12. Comercio, receita e faturamento

Planejar B2B, B2C, direto, catalogos, variantes, precos, promocoes, carrinho, checkout, pedidos, pagamentos por adaptadores, entrega, devolucao, disponibilidade, contratos, assinaturas, renovacao, consumo, faturamento, cobranca, creditos e comissoes.

Integrar estoque e financeiro sem duplicar conceitos. Regras fiscais e financeiras criticas exigem testes, validacao e provedores separados.

## 13. Projetos, estoque, financeiro e RH

### Projetos

Projetos, fases, tarefas, dependencias, equipes, horas, capacidade, riscos, custos, documentos, cronograma, automacoes, relatorios e agentes.

### Estoque

Produtos, depositos, enderecos, lotes, series, movimentos, reservas, inventarios, transferencias, pedidos, minimos, maximos, rastreabilidade, previsao e agentes.

### Financeiro

Contas a pagar/receber, categorias, centros de custo, caixa, conciliacao, cobrancas, orcamentos, contratos, recorrencia, relatorios, alertas e agentes. Acoes de alto impacto exigem aprovacao e auditoria.

### Recursos humanos

Colaboradores, equipes, cargos, competencias, documentos, admissoes, desligamentos, ferias, ausencias, avaliacoes, treinamentos, solicitacoes, aprovacoes e agentes. Dados pessoais exigem acesso, retencao e auditoria rigorosos.

## 14. Automacao empresarial

Manter o n8n oculto quando util, sem depender de seus formatos. Criar contratos proprios como `AutomationProvider`, `WorkflowEngine`, `TriggerRegistry`, `ActionRegistry`, `WorkflowPublisher` e `WorkflowExecutionService`.

O construtor deve oferecer gatilhos, condicoes, ramificacoes, loops controlados, esperas, agendas, acoes, transformacoes, subfluxos, APIs, dados, agentes, aprovacao, notificacoes e erros.

Cada automacao deve ter rascunho, versao, validacao, simulacao, teste, publicacao, ativacao, pausa, historico, rollback, logs, metricas e reprocessamento.

Implementar idempotencia, retries, timeout, circuit breaker quando necessario, DLQ, correlacao, tracing, concorrencia, limites, prioridade, cancelamento, compensacao e protecao contra loops. Nunca expor n8n ao usuario final.

## 15. Integracao e APIs

Construir catalogo de APIs, conectores, credenciais, webhooks, transformacoes, mapeamentos, sincronizacao, versao, documentacao, chaves, OAuth, escopos, rate limits, logs, metricas, politicas, filas, eventos, testes, ambientes e deploy.

Todo recurso importante deve possuir API autorizada. Evoluir REST, webhooks, eventos, OpenAPI, filtros, paginacao, ordenacao, selecao de campos, lotes, chaves de idempotencia, concorrencia, versao, erros e correlation IDs. Usar GraphQL apenas com beneficio comprovado.

SDK de conectores deve declarar manifesto, versao, autenticacao, acoes, gatilhos, schemas, testes, permissoes, limites, erros, documentacao, icone e atualizacao.

## 16. Arquitetura orientada a eventos

Comecar com eventos de dominio, transactional outbox, consumidores idempotentes, Redis/Celery existentes, DLQ e reprocessamento, preservando abstracao futura para Kafka, NATS, RabbitMQ ou outro broker.

Eventos devem conter identificador, tipo, versao, empresa, usuario, origem, correlacao, causalidade, data, payload validado, classificacao e retencao, sem dados sensiveis desnecessarios.

## 17. Runtime de agentes autonomos

Criar runtime independente de provedor, autonomo somente dentro de limites claros.

### 17.1 Estruturas

Definicoes, versoes, papeis, topicos, habilidades, ferramentas, politicas, agendas, gatilhos, memorias, fontes, execucoes, passos, chamadas, aprovacoes, handoffs, suites/casos de avaliacao, metricas, orcamentos e vinculos de credencial.

### 17.2 Configuracao

Cada agente deve definir nome, funcao, objetivo, departamento, empresa, supervisor, versao, idioma, modelos, topicos, tarefas, ferramentas, dados, canais, horarios, limites, orcamento, autonomia, aprovacao, memoria, retencao, sucesso, metricas, instrucoes e fallback.

### 17.3 Autonomia

- Nivel 0 - consulta;
- Nivel 1 - recomendacao;
- Nivel 2 - execucao supervisionada;
- Nivel 3 - autonomia controlada;
- Nivel 4 - coordenacao multiagente.

Configurar por agente, ferramenta e acao.

### 17.4 Fluxo obrigatorio

Autenticar origem, resolver empresa/usuario, carregar permissoes/politicas, classificar intencao, recuperar contexto/conhecimento autorizado, planejar, selecionar ferramentas, avaliar risco/orcamento, pedir aprovacao, executar, validar resultado, auditar, atualizar memoria permitida, concluir e registrar metricas.

### 17.5 Raciocinio hibrido

Combinar linguagem natural e planejamento com regras deterministicas, maquinas de estado, politicas, schemas, permissoes, limites e verificacao. O LLM nao controla sozinho processos criticos.

### 17.6 Ferramentas

Agentes nunca acessam o banco diretamente. Ferramentas tipadas e autorizadas declaram nome, descricao, versao, entrada, saida, permissoes, risco, aprovacao, simulacao, reversao, timeout, custo, limites e erro.

### 17.7 Seguranca

Menor privilegio, autorizacao por ferramenta/registro/campo, isolamento, mascaramento, protecao contra prompt injection, filtragem de documentos, validacao de saida, expiracao, segredos, retencao, auditoria, bloqueio de escopo, repeticao, custo, passos, tempo e chamadas externas. Instrucoes em conteudo externo nunca substituem politicas do sistema.

### 17.8 Memoria

Separar conversa, tarefa, usuario, empresa, operacao e conhecimento. Nunca compartilhar entre empresas. Permitir expiracao, revisao, exclusao, retencao, classificacao, consentimento e auditoria.

### 17.9 Conhecimento e RAG

Fontes, documentos, versoes, permissoes, chunks, indexacao, embeddings, filtros, citacoes, atualizacao, reindexacao, exclusao, avaliacao e obsolescencia.

### 17.10 Multiagentes

Supervisor, especialistas, delegacao, contratos, estado autorizado, mensagens, prazos, orcamento, revisao, consolidacao e escalonamento humano.

### 17.11 Simulacao e sombra

Simulacao, modo sombra, somente leitura, ambiente de teste, dados sinteticos, comparacao humana, canary e liberacao gradual.

### 17.12 Testes

Suites e casos com ferramentas esperadas/proibidas, resultados, avaliacoes deterministicas/por modelo, regressao, prompt injection, dados ruins, indisponibilidade, timeout, integracao, custo e tentativa cross-tenant. Nenhum agente publicado sem criterios aprovados.

### 17.13 Observabilidade

Painel de agentes, execucoes, sucesso, falha, aprovacao, handoff, custo, tokens, latencia, passos, ferramentas, erros, violacoes, feedback, produtividade e qualidade. Trace compreensivel sem expor raciocinio interno sensivel.

### 17.14 Trabalhadores digitais

Cargo, funcao, departamento, supervisor, jornada, fila, metas, SLAs, orcamento, ferramentas, indicadores, avaliacoes, escalonamentos, substitutos e calendario, distinguindo sempre acoes humanas e de agentes.

## 18. Provedores de inteligencia artificial

Criar abstracoes `ModelProvider`, `EmbeddingProvider`, `RerankingProvider`, `SpeechProvider`, `VisionProvider` e `ModerationProvider`.

Permitir modelo por empresa/agente/tarefa, fallback, roteamento por custo/latencia/capacidade, modelos externos/locais, consumo, direitos de plano e credenciais proprias ou administradas. Nunca gravar chaves em texto simples.

Politicas definem quais dados podem sair, mascaramento, provedor, local de processamento, retencao e modelos permitidos.

## 19. Seguranca empresarial

Seguranca deve ser aplicada no back-end. Suportar empresas, unidades, departamentos, equipes, usuarios, grupos, papeis, hierarquia, permissoes, permission sets, politicas, proprietarios, compartilhamento, delegacao e escopos.

Autorizar por aplicacao, modulo, objeto, registro, campo, acao, ferramenta, integracao, relatorio, dashboard, agente, documento e automacao. Acoes incluem ver, criar, editar, imprimir, excluir, administrar, exportar, importar, compartilhar, aprovar, executar, publicar e configurar.

Planejar MFA, SSO, OIDC, SAML, SCIM, sessoes, dispositivos, IPs, senhas, rotacao, criptografia, cofre, auditoria, acesso, retencao, backup, restauracao, classificacao, consentimento e anonimizacao.

Avaliar PostgreSQL RLS como defesa adicional, sem ativar antes de plano, testes, compatibilidade, estrategia de conexao e desempenho. Criar testes de acesso entre empresas.

## 20. Marketplace

Distribuir modulos, conectores, automacoes, modelos, dashboards, agentes, ferramentas, metadados e solucoes setoriais. Pacotes devem declarar identidade, desenvolvedor, versao, manifesto, dependencias, compatibilidade, permissoes, migracoes, assinatura, integridade, documentacao, atualizacao, remocao, testes e avaliacao de seguranca.

Instalacao valida pacote, compatibilidade, permissoes, dependencias e migracoes; registra versao, ativa, permite rollback e audita. Proibir codigo arbitrario sem isolamento e revisao.

## 21. Portais externos

Preparar portais de clientes, parceiros, fornecedores, colaboradores, candidatos, representantes e franquias, com dominio, identidade por empresa, autenticacao, autoatendimento, tickets, pedidos, documentos, contratos, pagamentos, conhecimento, formularios, aprovacoes, relatorios e colaboracao, sempre sob as politicas do nucleo.

## 22. Analytics

Incluir construtor de relatorios, tabelas, agrupamentos, matrizes, formulas, filtros, graficos, dashboards, drill-down, agendamento, exportacao, compartilhamento, alertas, metas, indicadores, comparacoes e tendencias.

Criar camada semantica central para metricas, dimensoes, formulas, periodos, moedas, metas e agregacoes.

Consultas em linguagem natural devem respeitar permissoes e mostrar dados que sustentam conclusoes.

## 23. Colaboracao

Comecar por colaboracao contextual: comentarios, mencoes, seguidores, atividades, feed, canais, equipes, anexos, notificacoes, presenca, aprovacoes, tarefas, conversas com agentes e compartilhamento de registros.

## 24. Plataforma para desenvolvedores

Fornecer documentacao, OpenAPI, SDK, CLI, webhooks, eventos, sandbox, ambientes, seeds, simuladores, metadados exportaveis, pacotes, versoes, feature flags, migracoes, testes e diagnostico.

Preparar desenvolvimento, teste, homologacao, producao e sandbox por empresa, com dados mascarados, promocao e rollback.

DevOps deve cobrir lint, tipos, testes unitarios/integracao/interface/migracao, seguranca, build, imagens, migration check, deploy, health, rollback e release notes.

## 25. Planos, assinaturas e uso

Suportar planos, trials, modulos, usuarios, armazenamento, automacoes, execucoes, agentes, ferramentas, tokens, mensagens, integracoes, APIs, limites, excedentes, creditos, periodo, renovacao, suspensao, grace period e entitlements.

Autorizacao de produto deve usar direitos no back-end. Uso deve ser idempotente e auditavel.

## 26. Arquitetura tecnica

Manter monolito modular ate existir justificativa real para microsservicos. Definir limites para identidade, empresas, permissoes, metadados, CRM, vendas, atendimento, marketing, comercio, financeiro, estoque, projetos, RH, analytics, automacoes, integracoes, agentes, conhecimento, marketplace, billing e auditoria.

Cada dominio deve possuir modelos, schemas, repositorios, servicos, politicas, rotas, eventos e testes conforme o padrao. Evitar regra em rota, acesso direto do front-end ao banco, agente escrevendo no banco, ciclos, imports cruzados e servicos sem responsabilidade clara.

## 27. Experiencia do usuario

Criar identidade propria e produtividade empresarial: navegacao global, seletor de aplicacao/empresa, pesquisa, acoes rapidas, favoritos, recentes, notificacoes, listas, filtros, tabela, kanban, calendario, paginas de registro, abas, historico, atividades, relacionamentos, painel lateral, teclado, responsividade e acessibilidade.

Portugues e o padrao. A tabela de usuarios deve permanecer ao lado da area de permissoes conforme o padrao do projeto.

## 28. Observabilidade e confiabilidade

Observar API, web, workers, filas, banco, Redis, n8n, integracoes, agentes, automacoes, arquivos e webhooks, com logs estruturados, correlation/trace IDs, metricas, health/readiness/liveness, alertas, latencia, erros, disponibilidade, filas, retries, DLQ e uso por empresa.

Planejar backup, restauracao testada, desastre, retencao, replicacao, deploy seguro, migracoes, rollback, degradacao, sobrecarga e limites. Falha de um tenant nao pode derrubar os demais.

## 29. Documentos obrigatorios

Manter:

- `docs/SALESFORCE_ORKESTRAL_EQUIVALENCE_MATRIX.md`;
- `docs/ORKESTRAL_TARGET_ARCHITECTURE.md`;
- `docs/ORKESTRAL_ENTERPRISE_ROADMAP.md`;
- `docs/ORKESTRAL_METADATA_PLATFORM.md`;
- `docs/ORKESTRAL_AGENTIC_RUNTIME.md`;
- `docs/ORKESTRAL_DATA_PLATFORM.md`;
- `docs/ORKESTRAL_SECURITY_MODEL.md`;
- `docs/ORKESTRAL_INTEGRATION_PLATFORM.md`;
- `docs/ORKESTRAL_AUTOMATION_ENGINE.md`;
- `docs/ORKESTRAL_MARKETPLACE.md`;
- `docs/ORKESTRAL_OBSERVABILITY.md`;
- `docs/ORKESTRAL_API_STANDARDS.md`;
- `docs/ORKESTRAL_DEFINITION_OF_DONE.md`;
- `docs/ORKESTRAL_IMPLEMENTATION_STATUS.md`.

Criar ADRs em `docs/adr/` para multiempresa, metadados, eventos/outbox, n8n, agentes, IA, memoria, vetores, RLS, marketplace, deploy e auditoria.

## 30. Roteiro de implementacao

### Fase 0 - Descoberta e estabilizacao

Inventario, testes, funcionalidades, incompletudes, Docker, banco, seguranca, permissoes, tenants, matriz, arquitetura, roadmap e divida.

### Fase 1 - Fundacao empresarial

Contexto da empresa, isolamento, permissoes, auditoria, eventos, erros, idempotencia, credenciais, jobs, health e testes entre empresas.

### Fase 2 - Plataforma de metadados

Entidades, campos, relacionamentos, layouts, visualizacoes, validacoes, registros, APIs, renderizacao, permissoes, publicacao e versao.

### Fase 3 - Eventos e automacoes

Eventos, transactional outbox, consumidores, engine canonico, adaptador n8n, versao, simulacao, aprovacao e observabilidade.

### Fase 4 - Runtime de agentes

Definicoes, versoes, ferramentas, politicas, execucao, memoria, conhecimento, aprovacao, auditoria, custos, testes e observabilidade.

### Fase 5 - Plataforma de dados

Modelo 360, identidade, ingestao, conectores, CDC, qualidade, linhagem, vetores, busca e ativacao.

### Fase 6 - Vendas

Leads, contas, oportunidades, produtos, precos, propostas, contratos, forecast e agentes comerciais.

### Fase 7 - Atendimento

Casos, SLA, filas, omnichannel, conhecimento, portal, agente e transferencia humana.

### Fase 8 - Marketing

Campanhas, segmentos, jornadas, canais, consentimento, personalizacao, analytics e agentes.

### Fase 9 - Receita e comercio

Catalogos, precos, pedidos, contratos, assinaturas, cobranca, pagamentos, estoque e financeiro.

### Fase 10 - Analytics e portais

Relatorios, dashboards, semantica, linguagem natural, portais e colaboracao.

### Fase 11 - Marketplace e desenvolvedores

Pacotes, versoes, assinatura, instalacao, SDK, CLI, sandbox e promocao.

### Fase 12 - Escala empresarial

SSO, SCIM, decisao RLS, recuperacao de desastre, alta disponibilidade, carga, seguranca, compliance, instalacoes dedicadas e setores.

## 31. Primeiro recorte de implementacao

Apos a Fase 0, implementar o primeiro recorte que desbloqueie a plataforma, priorizando conforme a realidade do repositorio:

1. contexto multiempresa;
2. permissoes no back-end;
3. auditoria unificada;
4. eventos com transactional outbox;
5. base de metadados;
6. testes de isolamento;
7. documentacao.

O recorte deve ser completo de ponta a ponta: banco, migracao, modelo, schema, servico, repositorio, rota, permissao, auditoria, evento, interface quando aplicavel, testes e documentacao.

## 32. Criterios gerais de aceitacao

Uma funcionalidade so esta pronta com requisitos, arquitetura, dados, migracao, validacao, servico, autorizacao, isolamento, auditoria, erros, idempotencia, API, interface quando aplicavel, testes unitarios/integracao/cross-tenant, documentacao, metricas, compatibilidade e avaliacao de seguranca.

Agentes tambem exigem ferramentas tipadas, politicas, limites, timeout, aprovacao, simulacao, trace e testes positivos, negativos, de injection, cross-tenant, indisponibilidade e resultado.

Integracoes tambem exigem credenciais criptografadas, timeout, retry, rate limit, idempotencia, logs protegidos, health, reprocessamento e revogacao.

## 33. Proibicoes tecnicas

Nao permitir:

- SQL sem filtro de empresa;
- autorizacao apenas visual;
- agentes irrestritos;
- segredos em codigo, logs ou respostas;
- financas autonomas sem politica;
- exclusao critica sem aprovacao;
- prompts com segredo;
- ferramenta sem schema;
- integracao sem timeout;
- job sem idempotencia;
- webhook sem validacao;
- migracao destrutiva sem estrategia;
- acoplamento direto a n8n ou provedor de IA;
- logica empresarial importante em rota;
- erro silencioso ou sucesso falso;
- regressao visual;
- nomes ou identidade da Salesforce na aplicacao.

## 34. Capacidades superiores priorizadas

1. Configuracao simples.
2. Portugues por padrao.
3. Automacao e IA em todos os modulos.
4. n8n oculto.
5. Agentes independentes de modelo.
6. SaaS, privada ou local.
7. Custos detalhados.
8. Modo sombra.
9. Simulacao antes da publicacao.
10. Explicacao das acoes.
11. Tracing completo.
12. Modulos por metadados.
13. Automacoes em linguagem natural.
14. Relatorios em linguagem natural.
15. Criacao assistida de agentes.
16. Agentes com cargo, supervisor, metas e orcamento.
17. Colaboracao entre agentes.
18. Marketplace unificado.
19. APIs abertas.
20. Independencia de fornecedor.
21. WhatsApp profundo.
22. Recursos brasileiros modulares.
23. Acessibilidade para PMEs.
24. Capacidade para grandes empresas.

## 35. Formato do trabalho

Para cada fase: analisar, documentar, decidir, implementar, migrar, testar, corrigir regressao, atualizar documentacao e status.

Manter `docs/ORKESTRAL_IMPLEMENTATION_STATUS.md` com fase, concluidos, parciais, pendentes, arquivos, migracoes, testes, resultados, riscos, divida e proximo passo exato.

O trabalho deve ocorrer em ciclos de tres entregas verificaveis. Ao concluir cada ciclo:

1. executar as verificacoes obrigatorias;
2. criar branch/commit/push e pull request;
3. mesclar automaticamente somente com verificacoes aprovadas e sem conflitos;
4. atualizar a base local;
5. continuar imediatamente do ponto seguinte.

Uma falha de teste, conflito, risco de perda ou decisao irreversivel bloqueia a mesclagem automatica, mas nao impede diagnostico e correcao segura.

## 36. Relatorio de cada ciclo

Apresentar:

- diagnostico inicial;
- comparacao e lacunas;
- arquitetura e decisoes;
- implementacao real;
- arquivos e migracoes;
- endpoints, telas, eventos, agentes e integracoes;
- comandos e resultados dos testes;
- falhas anteriores, regressao e correcoes;
- isolamento, permissoes, auditoria, segredos e riscos;
- fase, percentual realista, proximo passo, bloqueios e divida.

Nao dizer apenas que a arquitetura foi preparada. Diferenciar claramente planejado, parcial, implementado e validado.

## 37. Ordem imediata

1. Inspecionar completamente o repositorio.
2. Confirmar a arquitetura real.
3. Executar os testes existentes.
4. Identificar o estado dos containers.
5. Inventariar modulos e funcionalidades.
6. Analisar multiempresa e permissoes.
7. Analisar agentes, automacoes, integracoes e plugins.
8. Pesquisar capacidades oficiais atuais da referencia.
9. Criar a matriz de equivalencia.
10. Criar a arquitetura-alvo.
11. Criar o roadmap por dependencia.
12. Implementar o primeiro recorte fundamental.
13. Executar os testes.
14. Atualizar a documentacao.
15. Apresentar o relatorio completo.

Preservar tudo o que funciona, nao esconder limitacoes e nao parar em recomendacoes. Evoluir o Orkestral como plataforma original, segura, modular, auditavel e preparada para competir com grandes plataformas empresariais.
