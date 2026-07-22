# Motor de eventos e automações do Orkestral

Atualizado em 21 de julho de 2026.

## Objetivo

O Orkestral mantém uma definição canônica própria para automações e usa provedores, como o n8n, apenas como mecanismos de execução. O domínio não depende do formato interno, endereço ou credenciais do provedor.

O recorte do Ciclo 58 acrescenta a camada confiável que liga ações empresariais a consumidores e automações:

1. a transação de negócio grava um evento no `outbox_events`;
2. o dispatcher valida o contrato publicado do evento;
3. o evento é publicado no transporte interno;
4. assinaturas compatíveis geram registros em `event_deliveries`;
5. consumidores processam cada combinação evento/consumidor uma única vez;
6. falhas recebem retentativa exponencial e, ao esgotar o limite, seguem para DLQ;
7. o operador pode solicitar replay auditado sem alterar o evento original.

## Componentes

| Componente                          | Responsabilidade                                                         |
| ----------------------------------- | ------------------------------------------------------------------------ |
| `EventContract`                     | Schema versionado, classificação, compatibilidade e checksum do payload. |
| `EventSubscription`                 | Liga um tipo/versionamento a um consumidor de registro ou workflow.      |
| `OutboxEvent`                       | Evento imutável persistido na mesma transação da ação empresarial.       |
| `EventDelivery`                     | Estado individual de entrega, tentativas, trava, erro e replay.          |
| `EventConsumption`                  | Ledger idempotente por evento e nome do consumidor.                      |
| `WorkflowExecution.source_event_id` | Impede duas execuções do mesmo workflow para o mesmo evento.             |
| `EventConsumerRegistry`             | Resolve adaptadores sem acoplar o dispatcher ao consumidor.              |

## Contratos

- Tipos seguem o formato `dominio.acao`, por exemplo `contact.created`.
- A versão é inteira, crescente e imutável depois da publicação.
- O schema é um subconjunto JSON fortemente validado, limitado a 32 KiB e sem referências externas.
- Se não existe contrato publicado para um tipo legado, o comportamento anterior é preservado.
- Depois que um tipo passa a ser governado, toda versão precisa de contrato publicado.
- Payload inválido é bloqueado antes do transporte com código seguro, sem registrar seu conteúdo.
- Compatibilidade `backward` bloqueia remoção de campos, mudança de tipos e novos campos obrigatórios.

## Idempotência e consistência

- A entrega possui unicidade por `event_id` e `subscription_id`.
- O consumo possui unicidade por `event_id` e `consumer_name`.
- O workflow possui unicidade por empresa, workflow e evento de origem.
- Consumidores verificam o ledger antes de executar efeitos.
- Travas `FOR UPDATE SKIP LOCKED` permitem múltiplos workers sem consumo concorrente da mesma entrega.
- O dispatcher e o consumidor trabalham em lotes limitados.

## Retentativa, DLQ e replay

- Falhas transitórias aguardam um intervalo exponencial limitado a cinco minutos.
- Cada assinatura define de 1 a 25 tentativas.
- Ao atingir o limite, a entrega muda para `dead_letter`.
- Replay de entrega reutiliza a mesma entrega, zera as tentativas e incrementa `replay_count`.
- Replay de outbox cria um novo evento, com `causation_id` apontando para o evento original.
- Toda solicitação de replay gera auditoria de autorização.

## Segurança multiempresa

- Contratos, assinaturas, entregas, eventos e workflows são filtrados por `company_id`.
- A assinatura só aceita workflow ativo da mesma empresa.
- APIs exigem `events.view`, `events.configure` ou `events.replay`.
- A central não expõe payloads empresariais; mostra apenas metadados operacionais seguros.
- Eventos continuam rejeitando chaves sensíveis como senha, token e segredo.
- O transporte e as credenciais internas não aparecem para o usuário.

## APIs administrativas

- `GET /events/summary`
- `GET|POST /events/contracts`
- `POST /events/contracts/{id}/publish`
- `GET|POST /events/subscriptions`
- `PATCH /events/subscriptions/{id}`
- `GET /events/deliveries`
- `POST /events/deliveries/{id}/replay`
- `GET /events/outbox`
- `POST /events/outbox/{id}/replay`

## Operação

O Celery Beat agenda despacho e consumo a cada cinco segundos. O painel **Eventos** exibe contratos, assinaturas, fila, DLQ e outbox. A indisponibilidade do n8n afeta somente assinaturas do tipo workflow; assinaturas de ledger e o restante da API continuam operando.

## Próximos recortes

1. gatilhos canônicos de workflow configuráveis pelo construtor visual;
2. simulação de evento e pré-visualização das entregas antes da publicação;
3. cancelamento, compensação e reprocessamento em lote;
4. métricas por tipo, consumidor, latência e empresa;
5. adaptador de transporte substituível além do Redis Streams.
