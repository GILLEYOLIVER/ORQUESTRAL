# Ciclo 110 - Sandboxes e promocoes governadas

- sandboxes logicos por empresa, sem copia automatica de dados reais;
- politicas de dados `empty`, `synthetic` e `masked`;
- expiracao e arquivamento auditados;
- promocoes de metadados, automacoes, agentes e plugins por checksum;
- rotas de ambiente progressivas e separacao entre solicitante e aprovador;
- eventos transacionais e RLS forcado.

A aprovacao registra autorizacao, mas nao declara deploy concluido. Pipelines
posteriores devem marcar `applied` ou `failed` somente apos execucao real.
