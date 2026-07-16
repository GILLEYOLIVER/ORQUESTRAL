# Solução de problemas

## Docker não encontrado

Instale Docker Desktop, habilite containers Linux e confirme com `docker compose version`. Sem Docker ainda é possível executar testes unitários usando Node 24, pnpm 11, Python 3.13 e uv.

## `/ready` retorna 503

Consulte `checks` no corpo e os logs por `request_id`. Verifique `docker compose ps`, PostgreSQL e Redis. A resposta não inclui detalhes internos por segurança.

## A migração inicial falha

As extensões exigem um usuário PostgreSQL capaz de executar `CREATE EXTENSION`. O usuário criado pela imagem oficial possui essa permissão no ambiente local.

## A prévia autenticada retorna 404

Ela só existe no servidor Vite em modo development com `VITE_AUTH_PREVIEW_ENABLED=true`. Isso é intencional; o build de produção não contém uma porta de entrada simulada.

## O banco `n8n` não existe

O script de inicialização roda somente na primeira criação do volume PostgreSQL. Em um ambiente local descartável, remova deliberadamente os volumes e suba novamente. Não faça isso em ambientes com dados importantes.
