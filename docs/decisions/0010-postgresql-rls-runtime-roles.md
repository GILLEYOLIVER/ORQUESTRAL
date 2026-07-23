# ADR 0010 - RLS transacional com papeis de runtime

**Status:** aceito

## Decisao

O Orkestral passa a usar PostgreSQL Row-Level Security como segunda barreira de
isolamento, sem substituir os filtros por `company_id` e as permissoes do
backend. Cada requisicao autenticada seleciona um papel de banco sem login:

- `orkestral_tenant_runtime`: leitura e escrita sujeitas a RLS;
- `orkestral_tenant_read_only`: somente leitura sujeita a RLS.

O `company_id` validado na sessao e gravado em
`app.current_company_id` somente na transacao. O contexto e o papel sao
reaplicados automaticamente sempre que um commit ou rollback abre nova
transacao.

## Motivos

- um filtro esquecido na aplicacao nao deve revelar outro tenant;
- `WITH CHECK` deve impedir insercao ou mudanca de `company_id` cruzada;
- o acesso de socio precisa ser bloqueado tambem no banco;
- papeis sem login evitam novas senhas e continuam portaveis entre provedores
  PostgreSQL;
- o sistema continua compativel com o monolito modular e com o Docker local.

## Controles

- todas as tabelas com `company_id` recebem `ENABLE` e `FORCE ROW LEVEL SECURITY`;
- associacoes `crm_contact_tags` e `role_permissions` herdam o tenant do pai;
- uma politica permissiva concede o tenant atual e uma politica restritiva
  impede que politicas futuras ampliem esse limite por engano;
- ausencia de contexto produz zero linhas, nunca acesso global;
- o papel administrativo que executa a migracao recebe uma politica explicita
  para migracoes e jobs; ela deixa de valer depois de `SET LOCAL ROLE` na API;
- tabelas de tentativa de autenticacao e redefinicao de senha sao revogadas dos
  papeis de runtime;
- jobs administrativos continuam fora desses papeis e devem manter escopo
  explicito, idempotencia e auditoria.

## Limites e continuidade

Superusuarios PostgreSQL sempre podem ignorar RLS. O runtime HTTP deixa de usar
seus privilegios ao executar `SET LOCAL ROLE`, mas migracoes e jobs de sistema
continuam privilegiados. Uma fase futura separara tambem as credenciais de
login de migracao, API e worker. RLS e defesa em profundidade, nao substitui
RBAC, schemas estritos, consultas parametrizadas ou testes de isolamento.
