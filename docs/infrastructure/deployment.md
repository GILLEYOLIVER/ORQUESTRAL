# Deploy

## Fluxo gratuito ativo

1. Mudanças entram em `development` por pull request, sem publicar automaticamente.
2. O responsável escolhe um SHA completo já presente na branch privada `development`.
3. O deploy é iniciado manualmente no Render ou por `scripts/deploy-development-manual.sh SHA`.
4. O Render desativa Auto-Deploy ao receber um deploy hook com `ref=SHA`.
5. O entrypoint valida variáveis, aplica migrações com lock e executa o bootstrap idempotente.
6. O Render valida `/ready` antes de marcar o deploy como `Live`.
7. `scripts/verify-deployment.sh` confirma o SHA em `/system/version` e a prontidão.

Esse fluxo manual usa o plano Render Free e não depende de minutos do GitHub Actions. Em 20/07/2026, a
conta do GitHub informou indisponibilidade dos runners por limite de gastos ou pagamento. Nenhum
limite foi aumentado e nenhum meio de pagamento foi adicionado, preservando a regra de custo zero.

O deploy hook é um segredo. Ele deve existir somente no cofre do provedor ou no ambiente temporário
do comando e nunca pode ser escrito no repositório, histórico do shell, logs ou documentação.

## Fluxo completo preservado

Quando houver cota gratuita disponível, o workflow `CI` valida código, testes, integrações,
containers e contratos. `Publish images` pode construir, escanear e publicar `api`, `web` e
`remote` no GHCR por SHA, com proveniência. A implantação de desenvolvimento permanece manual:
`Deploy development` só aceita `workflow_dispatch` com SHA explícito.

Staging usa o workflow manual protegido `Deploy staging`. Ele aceita somente um SHA completo ja publicado, confirma as imagens imutaveis, cria backup, executa a migracao em tarefa unica, implanta e verifica o commit. O procedimento e os secrets exigidos estao em `docs/infrastructure/staging.md`.

Os workflows também podem ser iniciados por `workflow_dispatch` quando runners estiverem
disponíveis. Um deploy nunca é considerado concluído apenas porque a imagem iniciou.

## Desenvolvimento remoto ativo

- URL: `https://orkestral-development.onrender.com`.
- Branch: `development`.
- GitHub Environment: `development`, restrito à branch de mesmo nome.
- Deploy ativo: exclusivamente manual por SHA; Auto-Deploy desligado.
- Render: serviço Docker Free `orkestral-development`, conectado ao repositório privado e à branch
  `development`.
- Verificação: commit publicado em `/system/version` e dependências em `/ready`.

O histórico preserva as implantações anteriores. A partir de 22/07/2026, push e merge nunca são
considerados autorização de publicação; cada release exige ação manual e verificação do SHA.

Comando manual, mantendo o hook apenas no ambiente atual:

```bash
RENDER_DEPLOY_HOOK='valor-no-cofre' scripts/deploy-development-manual.sh SHA_COMPLETO
```

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

Em staging, use `action=rollback` no workflow `Deploy staging` com o ultimo SHA saudavel. O mesmo artefato homologado deve ser promovido para producao sem rebuild.

## Producao

Producao usa o workflow manual protegido `Deploy production`. Ele exige um SHA completo
publicado, o ultimo SHA saudavel, evidencia de staging, referencia de mudanca e confirmacao
explicita. O workflow verifica a proveniencia das imagens, cria backup, executa a migration em
tarefa unica, promove a release e valida versao e readiness.

Se a verificacao falhar, o ultimo SHA saudavel e restaurado automaticamente e a promocao permanece
com estado de falha para investigacao. Provisionamento, secrets, gates de lancamento e recuperacao
estao detalhados em `docs/infrastructure/production.md`.
