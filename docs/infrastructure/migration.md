# Migração e portabilidade

## Exportar

```bash
DATABASE_URL='postgresql://...' scripts/export-development-database.sh
```

O dump contém dados pessoais e credenciais criptografadas. Ele usa permissão local restrita, deve permanecer fora do Git e precisa ser apagado quando não for mais necessário.

## Restaurar em outro PostgreSQL

```bash
DATABASE_URL='postgresql://...' scripts/restore-development-database.sh arquivo.dump
```

Depois da restauração, execute migrations, `/ready`, login, isolamento entre empresas e um smoke test das rotas principais. Não reutilize `JWT_SECRET` e `ENCRYPTION_KEY` sem um plano explícito de rotação das credenciais criptografadas.

## Troca de provedor

1. Provisione PostgreSQL e Redis compatíveis.
2. Restaure o dump no novo banco.
3. Atualize somente variáveis do ambiente.
4. Publique a mesma imagem OCI.
5. Valide versão, saúde e autenticação antes de trocar DNS.

Nenhuma regra de negócio depende de SDK proprietário do Render, Neon ou Upstash.
