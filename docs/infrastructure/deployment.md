# Deploy

## Fluxo

1. Mudanças entram em `development` por pull request.
2. O workflow `CI` deve concluir com sucesso.
3. `Publish images` constrói, escaneia e publica `api`, `web` e `remote` no GHCR por SHA.
4. Cada imagem recebe uma attestação de proveniência.
5. `Deploy development` chama o deploy hook do Render somente depois da publicação.
6. O workflow usa `scripts/verify-deployment.sh` para confirmar `/system/version` e `/ready`.

O deploy também pode ser iniciado manualmente por `workflow_dispatch`. Um deploy nunca é considerado concluído apenas porque a imagem iniciou.

## Ambientes protegidos

Crie no GitHub os ambientes `development`, `staging` e `production`. Guarde hooks e URLs em secrets/variables do ambiente. Staging e produção devem exigir revisão e aceitar somente suas branches autorizadas. O ambiente `testing` é efêmero e não recebe segredos remotos.

Imagens publicadas:

```text
ghcr.io/<owner>/<repo>-api:sha-<commit>
ghcr.io/<owner>/<repo>-web:sha-<commit>
ghcr.io/<owner>/<repo>-remote:sha-<commit>
```

## Migrações e seed

O entrypoint executa `validate_deployment`, adquire um advisory lock PostgreSQL, aplica Alembic e faz bootstrap idempotente. O lock impede duas réplicas de migrarem simultaneamente.

No desenvolvimento gratuito, `RUN_MIGRATIONS_ON_STARTUP=true` é seguro porque existe uma única instância e o advisory lock permanece ativo. Em staging e produção use `false`: execute uma tarefa única com a mesma imagem e todos os secrets do ambiente antes de promover as réplicas.

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
