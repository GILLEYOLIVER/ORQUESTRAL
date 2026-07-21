# Inventario funcional dos modulos Orkestral

Data do inventario: 21 de julho de 2026.

Este documento registra o que existe no codigo hoje. Ele nao representa promessa comercial e nao usa a presenca de uma tela como prova de maturidade. Os niveis seguem a escala empresarial definida no Prompt Mestre.

## Escala de maturidade

| Nivel | Significado |
| --- | --- |
| 0 | Inexistente |
| 1 | Prototipo |
| 2 | Basico funcional |
| 3 | Equivalente essencial |
| 4 | Equivalente empresarial |
| 5 | Superior a referencia |

## Fundacao da plataforma

| Dominio | Implementado agora | Nivel | Lacuna principal |
| --- | --- | ---: | --- |
| Identidade e acesso | Login, refresh, logout, recuperacao, sessoes, selecao de empresa e acesso local de desenvolvimento | 2 | MFA, SSO, OIDC, SAML, SCIM e gestao de dispositivos |
| Empresas | Cadastro, atualizacao, selecao, contexto por empresa e eliminacao controlada de dados | 3 | Unidades, departamentos, delegacoes e politicas territoriais |
| Usuarios e papeis | Convites, membros, papeis, permissoes e papeis de sistema | 3 | Conjuntos de permissoes, hierarquia, compartilhamento por registro e campo |
| Auditoria | Eventos de autorizacao e eventos gerais, consulta e expurgo administrativo | 3 | Exportacao assinada, armazenamento imutavel e politicas por classificacao |
| Modulos | Catalogo, instalacao e ativacao por empresa | 2 | Dependencias versionadas, entitlements e promocao entre ambientes |
| Plugins e credenciais | Catalogo, ativacao, credenciais criptografadas, testes e rotacao | 2 | SDK, assinatura de pacote, isolamento de execucao e marketplace completo |
| Planos e consumo | Planos, assinaturas, cancelamento, uso e visao administrativa | 2 | Excedentes, grace period, creditos, faturamento e direitos granulares |
| Notificacoes e aprovacoes | Caixa pessoal, preferencias, lembretes, aprovacao humana e retomada de execucao | 3 | Escalonamento, delegacao, calendario e canais empresariais completos |

## Operacao empresarial

| Modulo | Implementado agora | Nivel | Lacuna principal |
| --- | --- | ---: | --- |
| CRM | Contatos, etiquetas, pipelines, etapas, oportunidades, atividades e indicadores basicos | 2 | Leads, contas, produtos, propostas, contratos, territorios e previsao inteligente |
| Suporte | Tickets, interacoes, filas, politicas de SLA, eventos, resposta e satisfacao | 2 | Roteamento por habilidade/carga, omnichannel completo, portal e atendimento de campo |
| Marketing | Campanhas, audiencia, jornadas, etapas, metricas, experimentos e atribuicao | 2 | Segmentacao avancada, consentimento completo, canais reais, frequencia e ROI empresarial |
| Projetos | Projetos, tarefas, portfolios, governanca, marcos, riscos, membros e dependencias | 2 | Capacidade, horas, custos, caminho critico, documentos e previsao de atraso |
| Estoque | Categorias, locais, itens, saldos e movimentos | 2 | Lotes, series, reservas, inventario, transferencias e reposicao inteligente |
| Financeiro | Contas, categorias, lancamentos, liquidacao, cancelamento e resumos | 2 | Conciliacao, recorrencia, cobranca, orcamentos e controles fiscais por adaptador |
| Recursos humanos | Departamentos, colaboradores, afastamentos e decisoes | 2 | Admissao, desligamento, ferias, competencias, avaliacao, treinamento e documentos |
| Analytics | Indicadores, medicoes, resumos e agregacao diaria | 2 | Construtor visual, camada semantica, dashboards configuraveis e linguagem natural |

## Inteligencia, conhecimento e automacao

| Dominio | Implementado agora | Nivel | Lacuna principal |
| --- | --- | ---: | --- |
| Agentes | Definicao, ferramentas, conversas, mensagens, execucao, aprovacao e consumo | 2 | Versoes, politicas por ferramenta, autonomia graduada, modo sombra, suites e multiagentes |
| Conhecimento | Bases, documentos, ingestao web, fragmentos, busca, reprocessamento e reindexacao | 2 | Vetores aprovados, citacoes completas, avaliacao RAG, linhagem e retencao granular |
| Automacoes | Definicao canonica, validacao, versoes, publicacao, execucao, rollback, webhooks e adaptador n8n | 3 | Simulacao visual completa, outbox, DLQ, compensacao e multiplos provedores de execucao |
| Integracoes | Credenciais por empresa e conectividade via plugins | 1 | Catalogo de APIs, OAuth, webhooks gerais, mapeamento, sincronizacao e SDK de conectores |

## Contratos transversais confirmados

- O PostgreSQL possui `company_id` indexado e ligado a `companies.id` em todas as tabelas empresariais diretas.
- Operacoes empresariais de escrita passam por permissao de tenant ou administracao de plataforma.
- Consultas empresariais exigem usuario autenticado.
- O n8n fica atras da definicao canonica de automacao e nao aparece como produto ao cliente.
- Credenciais de plugins sao cifradas antes da persistencia.
- A interface, API, worker e dependencias continuam executaveis por Docker Compose local.

## Regra de atualizacao

Atualize este inventario quando um modulo ganhar modelos, endpoints, telas ou testes relevantes. Um modulo somente sobe de nivel quando o recorte correspondente possuir banco, autorizacao, isolamento, auditoria, API, interface, testes e documentacao.
