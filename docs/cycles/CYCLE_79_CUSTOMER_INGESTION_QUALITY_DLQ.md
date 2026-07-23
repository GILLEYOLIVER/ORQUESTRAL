# Ciclo 79 - ingestao, qualidade e fila de erros

## Entrega

O ciclo cria uma entrada governada para dados de clientes:

- ingestao em lote ou incremental;
- chave de idempotencia por empresa;
- fontes de dados registradas;
- regras de qualidade versionadas;
- consolidacao imediata no perfil canonico;
- identidades protegidas por SHA-256;
- linhagem por campo;
- fila de erros sem carga bruta;
- reprocessamento com carga corrigida;
- contadores, auditoria e isolamento por RLS.

## Privacidade

A tabela de registros de ingestao nao armazena nome, e-mail, telefone ou a
carga JSON. Ela conserva somente o hash da carga, o identificador externo,
os codigos de validacao e o perfil consolidado. Um reprocessamento exige
que um usuario autorizado forneca novamente os dados corrigidos.

## Confiabilidade

- Uma chave de idempotencia repetida devolve o mesmo resultado.
- Cada identificador de origem aparece apenas uma vez no mesmo job.
- O conjunto de regras usado fica vinculado ao job.
- Uma regra publicada nunca e alterada silenciosamente.
- Reprocessamentos atualizam os contadores do job.
- Toda tentativa registra ator, motivo e numero da tentativa.

## Proximo passo

Adicionar conectores de ingestao agendada, cursores persistentes, limites de
concorrencia e observabilidade de sincronizacoes.

## Evidencias de validacao

- Backend, worker, integracao e seguranca: 250 testes aprovados com worker isolado.
- Operacao PostgreSQL: job parcial, idempotencia, rejeicao, correcao e reprocessamento aprovados com rollback total.
- Frontend: 19 testes aprovados e build de producao concluido.
- Qualidade: Ruff e mypy aprovados em 226 arquivos produtivos.
- Banco: downgrade para 20260723_0092 e upgrade para 20260723_0093 aprovados; 0093 permanece no head.
- Seguranca: auditoria de segredos, frontend, roles PostgreSQL, Node, Bandit e dependencias Python sem bloqueios.
- Contratos: OpenAPI e tipos TypeScript regenerados.
