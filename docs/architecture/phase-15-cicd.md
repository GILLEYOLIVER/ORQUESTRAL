# Fase 15 - CI/CD e deploy

## Decisão

O CI continua sendo a barreira obrigatória. Somente um SHA aprovado pode gerar imagens no GHCR, identificadas por componente e commit. Cada imagem recebe scan de vulnerabilidades críticas e proveniência do GitHub antes de ser considerada publicável.

## Fluxo

```text
pull request -> CI -> merge -> build/scan -> GHCR + attestation -> ambiente autorizado -> version/ready
```

São publicadas três imagens portáveis: `api`, `web` e `remote`. O deploy gratuito usa `remote`; as imagens separadas preservam a futura topologia de staging e produção.

## Promoção

- `development`: automática somente após `Publish images` verde na branch `development`, ou manual.
- `testing`: efêmero dentro do CI, sem segredos compartilhados.
- `staging`: preparado, manual e protegido por GitHub Environment.
- `production`: contrato preparado, sem provedor ou deploy automático nesta fase.

Migrações de desenvolvimento usam advisory lock PostgreSQL. Staging e produção devem executar uma única tarefa de migração antes de iniciar réplicas, mantendo `RUN_MIGRATIONS_ON_STARTUP=false`.

## Segurança

Os workflows usam permissões mínimas, `GITHUB_TOKEN` para GHCR, secrets por ambiente e imagens imutáveis por SHA. Nenhuma credencial de provedor integra o repositório.
