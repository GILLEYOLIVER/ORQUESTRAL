# Recuperacao de desastre

## Objetivo

Restaurar o Orkestral de forma comprovável, sem transformar a existência de um
arquivo de backup em falsa garantia de recuperação.

## Metas

RPO e RTO devem ser contratados por ambiente. A referência inicial para uma
instalação dedicada é RPO de 24 horas e RTO de 4 horas. Produção com exigência
maior precisa de backup contínuo do PostgreSQL, replicação e armazenamento
versionado fora do domínio de falha principal.

## Criar e verificar

```bash
./infrastructure/scripts/backup.sh
BACKUP_SCOPE=database ./infrastructure/scripts/backup.sh
uv run --project apps/api \
  python -m app.scripts.resilience verify-backup /caminho/do/backup
```

O PostgreSQL usa formato custom, sem proprietário ou ACL da origem. O diretório
usa modo `0700`, os arquivos `0600` e `SHA256SUMS` protege a integridade.

## Drill isolado

```bash
./infrastructure/scripts/restore-drill.sh /caminho/do/backup
```

O script cria um banco temporário, restaura o dump, verifica Alembic, tabelas e
RLS forçada, e remove o banco temporário ao sair. Ele não sobrescreve o banco ativo.

## Restauração real

```bash
CONFIRM_RESTORE=YES ./infrastructure/scripts/restore.sh /caminho/do/backup
```

Essa operação é deliberadamente destrutiva e exige incidente e janela aprovados.
Depois valide Alembic, auditoria de segurança, `/health`, `/ready`,
`/system/version`, login, isolamento entre empresas, objetos e integrações.

## Frequência

- integridade: a cada backup;
- restauração isolada: mensal em desenvolvimento e trimestral em produção;
- simulação completa: semestral;
- revisão de RPO/RTO: anual ou após mudança arquitetural relevante.

Nenhum drill deve usar dados reais fora do ambiente autorizado.
