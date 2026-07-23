# Ciclo 80 - Sincronizacao, agendamento e observabilidade de dados

## Objetivo

Transformar a ingestao governada do ciclo 79 em uma base operacional para
conectores empresariais, preservando isolamento, idempotencia e minimizacao de
dados.

## Entregas

- conectores por empresa e fonte canonica;
- transportes `push`, `pull` e `webhook`;
- referencia opcional a credencial cifrada existente;
- agenda persistente e proxima janela de execucao;
- lease exclusivo com token somente em memoria e SHA-256 no banco;
- cursores incrementais sem exibicao do valor bruto;
- execucao idempotente integrada a ingestao do ciclo 79;
- backoff exponencial limitado a 24 horas;
- pausa e retomada sem apagar historico;
- metricas agregadas e historico de execucoes;
- auditoria de criacao, mudanca de estado, sucesso e falha;
- RLS forcado nas tabelas novas.

## Limites conscientes

Este ciclo entrega o contrato seguro e uma entrada de dados real para
adaptadores. Ele nao afirma que um ERP foi consultado quando nenhum adaptador
esta instalado. O proximo recorte adicionara registro de adaptadores, scheduler
do worker e health por provedor.

## Seguranca

- nenhuma senha, token ou conteudo de credencial retorna pela API;
- nenhum lease bruto e persistido;
- cursores aparecem somente como fingerprint;
- a interface nao solicita segredos;
- a credencial, quando informada pela API administrativa, deve estar ativa na
  mesma empresa;
- respostas de execucao retornam contagens e codigos seguros, nunca a carga.

## Migracao

`20260723_0094` cria `customer_sync_connectors` e `customer_sync_runs`, com
restricoes, indices, chaves estrangeiras e politicas RLS reversiveis.

## Validacao

- 253 testes Python aprovados;
- 19 testes de interface aprovados;
- build de producao concluido;
- Ruff e mypy em 229 arquivos produtivos aprovados;
- rollback `0094 -> 0093 -> 0094` aprovado;
- sincronizacao real, idempotencia, lease, cursor, pausa e retomada aprovados;
- auditoria de segredos, dependencias e fronteira do navegador sem bloqueios;
- oito servicos locais ativos e endpoints de saude aprovados.
