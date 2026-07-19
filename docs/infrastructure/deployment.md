# Deploy

## Fluxo

1. Mudanças entram em `development` por pull request.
2. O workflow `CI` deve concluir com sucesso.
3. `Deploy development` chama o deploy hook do Render.
4. O workflow aguarda `/system/version` anunciar o SHA exato e confirma `/ready`.

O deploy também pode ser iniciado manualmente por `workflow_dispatch`. Um deploy nunca é considerado concluído apenas porque a imagem iniciou.

## Migrações e seed

O entrypoint executa `validate_deployment`, adquire um advisory lock PostgreSQL, aplica Alembic e faz bootstrap idempotente. O lock impede duas réplicas de migrarem simultaneamente.

Seed manual remoto:

```bash
cd apps/api
python -m app.scripts.seed_development
```

## Rollback

1. No Render, selecione o último deploy saudável e use rollback/redeploy.
2. Confirme `/system/version` e `/ready`.
3. Migrações devem ser retrocompatíveis; não reverta uma migration destrutiva sem restauração validada.
4. Se necessário, restaure um dump em um banco novo e altere `DATABASE_URL` somente após validar o novo banco.
