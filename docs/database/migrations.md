# Migrações do banco

Alembic é a única forma autorizada de alterar estruturas persistentes.

```bash
cd apps/api
uv run alembic -c alembic.ini upgrade head
uv run alembic -c alembic.ini downgrade -1
```

A migração inicial habilita `pgcrypto` e `citext`. Ela não cria tabelas de negócio. Novas migrações devem ter downgrade sempre que a reversão não causar perda de dados.
