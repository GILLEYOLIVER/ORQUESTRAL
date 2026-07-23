# Ciclo 85 - Manutencao automatica da retencao CDC

## Objetivo

Executar a politica segura do Ciclo 84 pelo worker a cada hora, sem retirar do
administrador a possibilidade de consultar a previa ou disparar um lote manual.

## Isolamento

- a descoberta global usa uma funcao `SECURITY DEFINER`;
- a funcao retorna somente `company_id`, nunca eventos ou dados de clientes;
- `PUBLIC` nao recebe permissao de execucao;
- somente a identidade PostgreSQL do worker recebe acesso quando ela existe;
- cada empresa e processada em sessao e transacao proprias;
- antes do expurgo, o worker define `app.current_company_id`;
- as tabelas continuam submetidas a RLS;
- uma falha incrementa a contagem e nao interrompe as outras empresas.

## Auditoria

Execucoes manuais guardam o usuario executor. Execucoes agendadas usam
`execution_source=scheduled` e nao personificam nenhum usuario.

## Agenda

Tarefa Celery:

`orkestral.customer_data.maintain_cdc_retention`

Intervalo:

`3600` segundos.

Cada empresa remove no maximo `1000` eventos por passagem.

