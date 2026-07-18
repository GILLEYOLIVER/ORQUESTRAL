# Base de conhecimento

Documentos PDF, DOCX, TXT, CSV e XLSX são validados, armazenados no MinIO e processados pelo worker Celery. Páginas web exigem HTTPS, domínio administrativo permitido e endereço público. O worker extrai texto, divide em chunks, gera embeddings determinísticos e registra erros.

Toda consulta combina `company_id`, base autorizada e documentos `ready`. O agente pesquisa somente a base vinculada em `knowledge_base_id`, recebe os trechos no contexto e anexa nomes e índices das fontes internas à resposta. Documentos podem ser removidos ou reenfileirados pelo endpoint de reprocessamento.
