# Ciclo 58 - Contratos e consumidores de eventos

## Estado

Implementado no código, aguardando validação completa, revisão e publicação.

## Entregue

- contratos de eventos por empresa, tipo e versão;
- schema forte, checksum e publicação com compatibilidade retroativa;
- assinaturas de ledger e workflow;
- entregas persistentes e concorrência com `SKIP LOCKED`;
- consumo idempotente;
- retentativa exponencial e DLQ;
- replay auditado e imutabilidade do evento original;
- origem idempotente em `WorkflowExecution`;
- worker e agenda de despacho/consumo;
- APIs com permissões e isolamento multiempresa;
- central visual responsiva;
- testes unitários e integração de segurança.

## Migração

`20260721_0078_event_contracts_consumers.py`

## Próximo passo exato

Adicionar gatilhos de eventos ao modelo canônico do construtor de automações, com simulação pré-publicação, políticas de concorrência e observabilidade de execução.
