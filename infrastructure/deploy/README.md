# Deploy remoto

O deploy de desenvolvimento usa a imagem única `Dockerfile.remote`: o React é compilado no primeiro estágio e servido pela API FastAPI no mesmo domínio. O Blueprint raiz `render.yaml` cria somente um Web Service gratuito e nunca cria banco, Redis ou armazenamento pagos.

Dependências externas: Neon PostgreSQL gratuito e Upstash Redis gratuito. n8n, worker, e-mail externo e armazenamento de objetos permanecem desligados pelas flags do ambiente.

Consulte `docs/infrastructure/remote-development.md` antes de provisionar.
