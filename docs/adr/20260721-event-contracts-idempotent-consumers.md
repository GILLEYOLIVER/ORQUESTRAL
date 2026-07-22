# ADR: contratos de eventos e consumidores idempotentes

- Data: 21 de julho de 2026
- Status: aceito
- Fase: 3 - Eventos e automações

## Contexto

O transactional outbox existente garantia que ações autorizadas produzissem eventos, mas não governava a evolução do payload, não materializava assinaturas e não oferecia processamento operacional com DLQ e replay. Ligar workflows diretamente ao Redis ou ao formato do n8n criaria acoplamento, duplicações em retentativas e risco de mistura multiempresa.

## Decisão

Adotar contratos JSON versionados por empresa e tipo, assinaturas declarativas e entregas persistentes. Consumidores são resolvidos por registro próprio e confirmados em um ledger idempotente. Workflows recebem `source_event_id`, tornando a execução repetível sem duplicar efeitos. O evento original nunca é reaberto para edição; replay cria uma nova causalidade ou reinicia somente o estado da entrega.

## Alternativas descartadas

- **Consumir Redis diretamente:** simples, mas perde rastreabilidade transacional e operação de DLQ.
- **Usar apenas idempotência do n8n:** acopla a confiabilidade ao provedor e não cobre outros consumidores.
- **Schema livre em JSON:** acelera o protótipo, mas permite contratos frágeis e mudanças incompatíveis.
- **Kafka imediato:** adiciona custo operacional antes de existir volume que o justifique.

## Consequências

Positivas:

- contratos publicados e imutáveis;
- isolamento por empresa em todas as entidades;
- processamento concorrente seguro;
- retentativa e replay auditáveis;
- n8n permanece oculto e substituível.

Custos:

- três tabelas e um vínculo adicional em execuções;
- monitoramento periódico do backlog;
- necessidade de evoluir o validador de schemas de forma controlada.

## Controles

- testes de payload e compatibilidade;
- testes de consumo único;
- testes de acesso cruzado;
- permissões separadas para leitura, configuração e replay;
- nenhum payload exibido na central operacional.
