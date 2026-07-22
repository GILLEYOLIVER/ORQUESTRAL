# Ciclo 61 - Resiliencia de automacoes

## Objetivo

Reduzir falhas em cascata, permitir retentativas controladas e formalizar as capacidades reais de cancelamento do provider.

## Entregue

- politica de retry por bloco com limite de tentativas e espera;
- compilacao para propriedades nativas do adaptador quando suportadas;
- circuit breaker persistente por empresa e provider;
- estados `closed`, `open` e `half_open` com recuperacao controlada;
- abertura somente para indisponibilidade, rede ou timeout;
- falhas funcionais nao contaminam a saude do provider;
- status do circuito exposto de forma segura no Estudio;
- contrato de cancelamento remoto com capacidade explicita;
- estado `unsupported` quando o provider nao oferece operacao publica confiavel;
- migracao reversivel `20260722_0080`.

## Decisao sobre n8n

Em 22 de julho de 2026, a documentacao publica consultada nao forneceu um contrato estavel para interromper antecipadamente a execucao iniciada pelo webhook usado no Orkestral. Endpoints privados `/rest` nao serao utilizados. O cancelamento cooperativo permanece ativo e a interface informa a limitacao.

Referencias oficiais consultadas:

- <https://docs.n8n.io/api/api-reference/>;
- <https://docs.n8n.io/workflows/executions/all-executions/>.

## Seguranca

- circuitos sao isolados por `company_id`;
- apenas codigos de falha, contadores e datas sao persistidos;
- o circuito impede novas chamadas durante a janela de protecao;
- retry possui limites estritos e nao aceita valores arbitrarios;
- cancelamento nunca retorna confirmacao falsa.

## Proximo passo exato

Concluir a Fase 3 com compensacoes vinculadas a blocos, testes de portabilidade com provider falso e indicadores operacionais globais sem payload empresarial.
