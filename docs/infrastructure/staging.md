# Staging

## Objetivo

Staging homologa exatamente as imagens que podem seguir para producao. O ambiente usa somente dados ficticios, infraestrutura e credenciais isoladas e HTTPS obrigatorio.

## Recursos obrigatorios

- PostgreSQL isolado, com backup e restauracao testados.
- Redis isolado.
- Runtime capaz de executar as imagens imutaveis `api`, `web` e `remote` do GHCR.
- Tarefa unica de migracao usando a mesma imagem da API.
- Dominio HTTPS separado, logs e alertas do ambiente.
- Hooks autenticados para backup, migracao, deploy e rollback.

## GitHub Environment

Crie o environment protegido `staging`, restrinja a branch a `main` e exija aprovacao. Cadastre:

| Tipo     | Nome                     | Finalidade                        |
| -------- | ------------------------ | --------------------------------- |
| Variable | `STAGING_BASE_URL`       | URL HTTPS publica do ambiente     |
| Secret   | `STAGING_HOOK_TOKEN`     | Token exclusivo dos hooks         |
| Secret   | `STAGING_BACKUP_HOOK`    | Cria backup antes da migracao     |
| Secret   | `STAGING_MIGRATION_HOOK` | Executa Alembic como tarefa unica |
| Secret   | `STAGING_DEPLOY_HOOK`    | Implanta o SHA informado          |
| Secret   | `STAGING_ROLLBACK_HOOK`  | Reimplanta um SHA anterior        |

Os hooks devem rejeitar tags mutaveis e aceitar apenas `release_sha` completo. Nenhum valor real deve ser salvo no repositorio.

## Promocao

1. Confirme que o commit em `main` passou no CI e no workflow `Publish images`.
2. Execute `Deploy staging` com `action=deploy` e o SHA completo.
3. Aprove o GitHub Environment.
4. O workflow confirma as tres imagens, cria backup, migra, implanta e valida versao e prontidao.
5. Execute smoke tests de login, isolamento multiempresa, automacoes, agentes, billing e notificacoes.
6. Registre o SHA homologado para a auditoria de seguranca.

## Rollback

Execute `Deploy staging` com `action=rollback` e o ultimo SHA saudavel. O workflow nao desfaz migracoes: toda migracao deve ser retrocompativel. Em incidente de dados, restaure o backup em banco novo, valide-o e somente entao altere a conexao.

Staging so esta provisionado quando os recursos externos forem autorizados, os secrets forem cadastrados e um deploy mais rollback tiverem sido executados com sucesso.
