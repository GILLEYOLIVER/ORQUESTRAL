# Ciclo 68 - Reconciliacao e controles do despacho de agentes

## Objetivo

Tornar a fila do runtime de agentes segura diante de reinicios e permitir que o
administrador configure execucoes de agenda e gatilho sem depender de valores
ocultos.

## Entrega

- despachos abandonados em `processing` sao identificados depois do tempo
  maximo do agente, acrescido de uma margem operacional;
- a recuperacao e fail-closed: o despacho e a execucao terminam como falha e
  exigem revisao manual;
- ferramentas externas nunca sao repetidas automaticamente depois de uma
  interrupcao cujo resultado possa ser desconhecido;
- reservas de custo sao liberadas sem registrar consumo ficticio;
- a recuperacao cria passo de trace, auditoria de autorizacao e evento de
  dominio `agent.dispatch.interrupted`;
- o evento informa `manual_review_required` como politica de repeticao;
- agendas e gatilhos permitem escolher modo sombra ou execucao real;
- execucoes reais aceitam percentual canario;
- argumentos por ferramenta sao informados como JSON e validados antes do
  envio;
- a fila recente mostra estados de preparacao, aprovacao, processamento,
  simulacao, conclusao e falha, com tentativa e motivo.

## Seguranca

- nenhuma execucao externa incerta e repetida silenciosamente;
- o identificador da empresa permanece em despachos, execucoes, auditoria e
  eventos;
- argumentos aceitam apenas ferramentas declaradas no agente;
- cada conjunto de argumentos deve ser um objeto JSON;
- o reconciliador usa bloqueio de linhas com `skip_locked` para evitar
  processamento concorrente;
- custos reservados sao liquidados de forma idempotente.

## Validacao

- teste unitario do limite temporal da reconciliacao;
- teste de interface para JSON valido, ferramenta nao autorizada e argumento
  escalar;
- teste de integracao com execucao sombra, trace, isolamento entre empresas e
  reconciliacao de interrupcao;
- verificacao de auditoria e evento pelo identificador exato do despacho.

## Proximo passo

Adicionar uma operacao administrativa explicitamente autorizada para revisar
despachos interrompidos, decidir entre encerrar ou repetir e exigir nova
aprovacao antes de qualquer repeticao de ferramenta externa.
