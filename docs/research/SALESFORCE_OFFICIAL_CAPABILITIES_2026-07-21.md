# Pesquisa oficial de capacidades empresariais

Data da verificacao: 21 de julho de 2026.

## Escopo e metodo

Esta pesquisa usa documentacao oficial da Salesforce, Salesforce Architects, Salesforce Developers e MuleSoft. Ela serve como referencia de problemas resolvidos e principios arquiteturais. Nomes comerciais permanecem somente neste documento interno; a implementacao e a interface do Orkestral devem ser originais.

## Conclusoes arquiteturais

### Multiempresa e metadados

A arquitetura oficial descreve uma plataforma multi-tenant orientada por metadados, com identificador do tenant aplicado a dados e definicoes. Tambem separa o kernel administrado pela plataforma dos metadados administrados por cada tenant. Para o Orkestral, isso reforca:

- manter `company_id` como limite obrigatorio;
- criar um kernel estavel e metadados versionados por empresa;
- gerar UI, validacao e APIs a partir do mesmo contrato;
- permitir extensao sem alterar tabelas e telas manualmente a cada caso;
- adicionar defesa no banco e testes negativos, nao apenas filtros no front-end.

Fonte: [Platform Multitenant Architecture](https://architect.salesforce.com/docs/architect/fundamentals/guide/platform-multitenant-architecture.html).

### Seguranca em camadas

A documentacao distingue seguranca de objeto, campo e registro, com permission sets e regras de compartilhamento. O Orkestral possui permissoes de modulo/acao e filtro por empresa, mas precisa evoluir para:

- permissao por objeto e campo;
- propriedade e compartilhamento de registro;
- hierarquia e conjuntos de permissoes;
- politicas de ferramenta, agente, documento e integracao;
- administracao de alto privilegio mais segmentada.

Fonte: [Platform Sharing Architecture](https://architect.salesforce.com/docs/architect/fundamentals/guide/platform-sharing-architecture).

### Agentes, testes e governanca

A documentacao atual permite definir testes de agente, executar por CLI/API, verificar topicos, acoes, resultados, latencia e criterios personalizados. A arquitetura oficial tambem enfatiza gateway de modelos, controle de custo, validacao de saida, observabilidade, supervisao humana e trilha verificavel.

Implicacoes para o Orkestral:

- agentes devem possuir versoes e suites antes de publicacao;
- testes precisam declarar ferramentas esperadas e proibidas;
- avaliacao deve combinar regras deterministicas e modelos;
- traces mostram objetivo, acoes e resultados, sem revelar raciocinio interno;
- autonomia precisa ser graduada e limitada por politica e orcamento;
- modelos devem permanecer substituiveis.

Fontes:

- [Get Started with Testing Agents](https://developer.salesforce.com/docs/ai/agentforce/guide/testing-api-get-started.html)
- [Run Agent Tests](https://developer.salesforce.com/docs/einstein/genai/guide/agent-dx-test-run.html)
- [Custom Evaluation Criteria](https://developer.salesforce.com/docs/einstein/genai/guide/testing-api-custom-evaluation-criteria.html)
- [Agentic Enterprise IT Architecture](https://architect.salesforce.com/docs/architect/fundamentals/guide/agentic-enterprise-it-architecture.html)
- [Models and Prompts](https://developer.salesforce.com/docs/einstein/genai/guide/models-get-started.html)

### Plataforma de dados e identidade

O modelo oficial separa objetos ingeridos, objetos harmonizados, perfis unificados e metricas calculadas. A resolucao de identidade usa mapeamento, regras de correspondencia e reconciliacao antes de formar um perfil unificado.

Implicacoes para o Orkestral:

- criar modelo canonico para pessoa, organizacao, identidade e pontos de contato;
- preservar fonte, chave externa, linhagem e qualidade;
- distinguir dado copiado, cacheado e consultado na origem;
- versionar regras de matching, merge e reconciliacao;
- manter consentimento, retencao, anonimizacao e exclusao por empresa.

Fontes:

- [Object Model in Data 360](https://developer.salesforce.com/docs/data/data-cloud-dev/guide/dc-object-model.html)
- [Data 360 Architecture](https://architect.salesforce.com/docs/architect/fundamentals/guide/data-360-architecture)
- [Identity Resolution](https://developer.salesforce.com/blogs/2024/10/data-cloud-and-identity-resolution)

### Eventos e processamento assincrono

A orientacao oficial recomenda eventos para desacoplamento, volume e atualizacao proxima de tempo real, mas nao como solucao universal. Ela destaca publicacao apos commit, payload minimo, convencoes, replay, filas e cuidado com loops.

Implicacoes para o Orkestral:

- iniciar com transactional outbox no PostgreSQL;
- publicar somente depois de transacao confirmada;
- usar consumidores idempotentes, replay e DLQ;
- versionar tipo e payload;
- escolher sincrono, lote ou evento conforme o caso;
- impedir loops entre evento e automacao.

Fontes:

- [Event-Driven Architecture Decision Guide](https://architect.salesforce.com/docs/architect/decision-guides/guide/event-driven)
- [Integration Patterns](https://architect.salesforce.com/docs/architect/fundamentals/guide/integration-patterns)
- [Asynchronous Processing](https://architect.salesforce.com/docs/architect/fundamentals/guide/async-fundamentals)

### Governanca de APIs e integracoes

A documentacao MuleSoft trata politicas fora da implementacao da API, incluindo autenticacao, trafego, SLA, logging e analytics. Tambem oferece regras de governanca desde especificacao ate implantacao e retentativas com resultado explicito quando esgotadas.

Implicacoes para o Orkestral:

- catalogar APIs, versoes, ambientes e contratos;
- aplicar autenticacao, rate limit e logging como politicas comuns;
- validar OpenAPI e conectores na CI;
- medir conformidade e violacoes;
- padronizar timeout, retry, idempotencia e erro;
- manter gateway e runtime substituiveis.

Fontes:

- [Mule Gateway Policies Overview](https://docs.mulesoft.com/mule-gateway/policies-policy-overview)
- [Anypoint API Governance Overview](https://docs.mulesoft.com/api-governance/)
- [Business Events](https://docs.mulesoft.com/mule-runtime/latest/business-events)
- [Until Successful Scope](https://docs.mulesoft.com/mule-runtime/latest/until-successful-scope)

## Matriz resumida da pesquisa

| Capacidade de referencia        | Orkestral atual                                        | Nivel | Proximo passo original                            |
| ------------------------------- | ------------------------------------------------------ | ----: | ------------------------------------------------- |
| Kernel multi-tenant e metadados | Kernel modular e `company_id`; sem plataforma dinamica |     1 | Definicoes versionadas e renderer compartilhado   |
| Seguranca objeto/campo/registro | Permissao por acao e tenant                            |     2 | Policy engine e compartilhamento granular         |
| Agentes com acoes               | 3 ferramentas tipadas e aprovacao                      |     2 | Versoes, politicas, budgets e catalogo extensivel |
| Testes de agentes               | Testes tecnicos do runtime                             |     1 | Suites funcionais, ataques e gates de publicacao  |
| Observabilidade de agentes      | Tokens, custo, duracao e runs de ferramenta            |     2 | Trace, metricas, violacoes e painel operacional   |
| Modelo de dados unificado       | Dominios separados                                     |     1 | Identidade canonica, fontes, matching e linhagem  |
| Eventos empresariais            | Execucoes e filas sem outbox canonica                  |     1 | Outbox, consumidores, DLQ e replay                |
| Automacao visual                | 16 blocos e definicao canonica                         |     3 | Simulacao, confiabilidade e provedores multiplos  |
| Governanca de API               | OpenAPI e permissoes de rota                           |     1 | Catalogo, politicas, conformidade e ambientes     |
| Credenciais e conectores        | 7 plugins e cofre cifrado                              |     2 | SDK, OAuth, schemas, rate limit e revogacao       |

## Decisoes para o roadmap

1. Plataforma de metadados e seguranca granular sao fundacao, nao acabamento.
2. Eventos devem entrar antes de ampliar automacoes e agentes autonomos.
3. O runtime de agentes deve ser hibrido: IA interpreta; politicas e maquinas de estado controlam.
4. A plataforma de dados deve preservar fonte e consentimento antes de unificar perfis.
5. Integracoes precisam de governanca e observabilidade comuns antes de aumentar o catalogo.
6. A implementacao continua como monolito modular; microsservicos somente por necessidade medida.

## Regra de manutencao

Revalidar estas fontes antes de cada grande fase comparativa. Produtos, nomes e limites mudam; os principios adotados no Orkestral devem permanecer independentes de fornecedor.
