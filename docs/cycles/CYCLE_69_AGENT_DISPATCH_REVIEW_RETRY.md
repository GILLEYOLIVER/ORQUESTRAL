# Ciclo 69 - Revisao e repeticao controlada de despachos

## Objetivo

Permitir que uma interrupcao incerta seja analisada sem reutilizar o despacho
falho e sem repetir silenciosamente uma operacao externa.

## Fluxo

1. o reconciliador do Ciclo 68 marca a execucao como
   `execution_interrupted_manual_review`;
2. um usuario com `agents.configure` registra motivo e decide encerrar ou
   preparar repeticao;
3. a decisao e imutavel para o despacho interrompido e possui chave de
   idempotencia;
4. quando a decisao e repetir, o estado fica `pending_approval`;
5. um usuario com `agents.execute` concede aprovacao explicita e idempotente;
6. credenciais e ferramentas sao verificadas novamente;
7. um novo despacho e criado com `source_type=retry` e
   `retry_of_dispatch_id`;
8. o executor normal reaplica orcamento, politicas, aprovacoes de ferramenta e
   trace.

## Garantias

- o despacho interrompido nunca volta para a fila;
- cada despacho interrompido recebe no maximo uma decisao;
- solicitacao e aprovacao usam chaves de idempotencia independentes;
- outra empresa recebe 404 e nao descobre a existencia da revisao;
- a repeticao possui identidade, timestamps, trace e estado proprios;
- auditoria e eventos registram decisao, aprovacao e linhagem;
- uma credencial revogada produz despacho bloqueado, nao execucao enganosa;
- a interface separa permissao de configurar da permissao de executar.

## Dados

- nova tabela `agent_dispatch_reviews`;
- nova autorreferencia `agent_runtime_dispatches.retry_of_dispatch_id`;
- indices unicos parciais preservam deduplicacao de agendas e eventos, sem
  impedir repeticoes explicitamente aprovadas;
- migracao Alembic `20260722_0085`.

## Interface

A fila segura recente mostra:

- origem Agenda, Evento ou Repeticao autorizada;
- formulario de motivo para interrupcoes revisaveis;
- decisoes Encerrar sem repetir e Preparar repeticao;
- estado pendente de aprovacao;
- botao Aprovar nova execucao somente para `agents.execute`;
- resultado encerrado ou aprovado para usuarios somente leitura.

## Validacao

- isolamento entre empresas;
- idempotencia da solicitacao;
- conflito de segunda decisao;
- idempotencia da aprovacao;
- criacao de nova linhagem;
- execucao sombra somente depois da aprovacao;
- lint, tipos e testes da interface.

## Proximo passo

Criar metricas e alertas para revisoes pendentes, tempo ate decisao, taxa de
repeticao e reincidencia por ferramenta, sem incluir argumentos sensiveis.
