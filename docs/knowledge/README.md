# Base de conhecimento

Documentos PDF, DOCX, TXT, CSV e XLSX são validados, armazenados no MinIO e processados pelo worker Celery. Páginas web exigem HTTPS, domínio administrativo permitido e endereço público.

## Embeddings e busca

Os chunks usam `vector(384)` no PostgreSQL com extensão `pgvector` e índice HNSW por distância de cosseno. A consulta é executada no banco e sempre filtra `company_id`, `knowledge_base_id` e documentos `ready` antes da ordenação vetorial.

Provedores:

- `local_hash`: fallback determinístico identificado, exclusivo para desenvolvimento e testes;
- `openai_compatible`: endpoint real `/embeddings`, obrigatório em produção.

A migração `20260718_0013` remove apenas chunks derivados incompatíveis e preserva documentos no MinIO. Bases existentes podem ser reenfileiradas por `POST /api/knowledge-bases/{base_id}/reindex`.

Variáveis: `KNOWLEDGE_EMBEDDING_PROVIDER`, `KNOWLEDGE_EMBEDDING_MODEL`, `KNOWLEDGE_EMBEDDING_DIMENSIONS` e `KNOWLEDGE_EMBEDDING_BATCH_SIZE`.
