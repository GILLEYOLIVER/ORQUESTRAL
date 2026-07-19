# ADR 0009 — pgvector para busca da base de conhecimento

**Status:** aceito

## Decisão

Embeddings são armazenados como `vector(384)` no PostgreSQL com `pgvector` e índice HNSW de cosseno. A busca ocorre em SQL depois dos filtros de `company_id`, base e estado do documento.

## Motivo

O banco já faz parte da infraestrutura e preserva transações, backup e isolamento lógico sem introduzir um serviço vetorial externo nesta fase. A implementação anterior em JSONB carregava até 2.000 chunks para a memória da API e não tinha índice, portanto não era adequada para crescimento.

`local_hash` continua disponível apenas como fallback explícito de desenvolvimento. Produção exige provedor `openai_compatible`, modelo e chave configurados. Dimensão, modelo e provedor são registrados nos metadados do documento para permitir reindexações futuras.

## Consequências

- troca de modelo ou dimensão exige reindexação controlada;
- documentos fonte permanecem no MinIO, enquanto chunks podem ser reconstruídos;
- backups do PostgreSQL precisam incluir a extensão `vector` no ambiente de restauração;
- um serviço vetorial dedicado só será considerado após métricas demonstrarem necessidade.
