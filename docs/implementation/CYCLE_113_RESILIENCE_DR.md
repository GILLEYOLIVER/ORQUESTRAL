# Ciclo 113 - Resiliencia, recuperacao e operacao dedicada

Data: 29 de julho de 2026.

## Entrega

- backup PostgreSQL em formato custom portátil e verificável;
- compatibilidade de restauração com o formato legado;
- verificador de integridade, permissões e caminhos seguros;
- drill em banco temporário sem sobrescrever o banco ativo;
- smoke concorrente e somente leitura para health/readiness;
- contrato dedicado independente de provedor;
- runbooks de recuperação, incidente, SLO e capacidade.

## Segurança

Artefatos são privados; manifesto só aceita nomes conhecidos; links simbólicos
e TAR traversal são rejeitados. O drill verifica RLS após restaurar. Nenhum
segredo ou URL com credencial é emitido. A restauração real continua exigindo
`CONFIRM_RESTORE=YES`.

## Critério de saída

Testes unitários, auditoria, backup, restauração isolada, smoke de carga,
migrações e runtime local precisam ser aprovados.

## Evidência executada

- MyPy: 336 fontes aprovadas;
- API: 346 testes aprovados;
- web: 19 testes, TypeScript e build aprovados;
- backup: formato custom e SHA-256 aprovados;
- restauração: revisão `20260729_0124`, 253 tabelas e zero falha de RLS;
- carga: 200 requisições, zero erro e p95 de 271,2 ms;
- segurança: segredos, frontend, papéis PostgreSQL, 237 tabelas tenant, Actions,
  Node, Bandit e dependências Python sem bloqueios;
- produção: contrato de prontidão aprovado.

O bundle web continua com aproximadamente 1,15 MB antes de gzip. A formatação
global também possui dívida histórica em 112 arquivos fora deste ciclo; todos
os arquivos Python alterados neste ciclo passam Ruff e formatação.
