# Definicao de pronto empresarial

Uma capacidade só está pronta quando possui requisitos, modelo e migração,
validação, serviço, autorização backend, isolamento por empresa, auditoria,
erros seguros, idempotência quando aplicável, API, interface aplicável, testes,
documentação, métricas e avaliação de segurança.

## Escala empresarial

Uma implantação só pode ser promovida quando:

- o backup mais recente passa na verificação criptográfica;
- uma restauração isolada comprova schema, Alembic e RLS;
- o smoke de carga respeita taxa de erro e p95 aprovados;
- `/health`, `/ready` e `/system/version` identificam a versão real;
- segredos, papéis de banco e isolamento passam na auditoria;
- RPO, RTO, SLO, capacidade, responsáveis e rollback estão documentados;
- instalação dedicada não compartilha credenciais nem armazenamento.

Documentação sem execução comprovada não satisfaz esta definição.
