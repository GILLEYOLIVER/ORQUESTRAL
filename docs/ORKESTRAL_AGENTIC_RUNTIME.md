# Runtime Agentico do Orkestral

## Objetivo

O runtime executa agentes empresariais dentro de limites explícitos de empresa, permissão, versão, risco e orçamento. O modelo de IA interpreta solicitações, mas não recebe autoridade direta sobre o banco nem substitui as políticas determinísticas.

## Contratos implantados no ciclo 10

### Versões

- Cada agente possui uma versão publicada identificada por `active_version_id`.
- Instruções, provedor, modelo, memória, base de conhecimento e limites são congelados em `agent_versions`.
- Novas versões começam como `draft` e somente a publicação altera a configuração executada.
- A versão anteriormente publicada passa para `retired`.
- Um checksum SHA-256 permite verificar a integridade da configuração.
- O histórico não guarda credenciais e eventos de publicação contêm somente identificadores e controles não secretos.

### Autonomia

| Nível | Comportamento                                                            |
| ----- | ------------------------------------------------------------------------ |
| 0     | Consulta, sem chamada de ferramenta                                      |
| 1     | Recomendação, sem execução                                               |
| 2     | Toda execução exige aprovação humana                                     |
| 3     | Ações de baixo e médio risco podem executar; alto risco exige aprovação  |
| 4     | Coordenação controlada; ações de alto risco continuam exigindo aprovação |

Ferramentas possuem risco `low`, `medium`, `high` ou `critical`. O back-end aplica a decisão mesmo que um cliente tente contornar a interface.

### Orçamento

- Cada agente possui orçamento mensal em microunidades de dólar.
- `hard_limit=true` impede uma execução antes de chamar o provedor quando a reserva ultrapassaria o saldo.
- A reserva usa `max_cost_per_run_microunits` da versão publicada.
- Depois da resposta do provedor, a reserva é trocada pelo custo real.
- Falhas conhecidas do provedor liberam a reserva.
- O ciclo é reiniciado automaticamente na primeira execução após o vencimento.

## API administrativa

- `GET /agents/{agent_id}/versions`
- `POST /agents/{agent_id}/versions`
- `POST /agents/{agent_id}/versions/{version_id}/publish`
- `GET /agents/{agent_id}/budget`
- `PUT /agents/{agent_id}/budget`

Todos os acessos são filtrados por `company_id` e exigem `agents.configure`. A execução continua exigindo `agents.execute` e a permissão específica de cada ferramenta.

## Próximos incrementos

- políticas de aprovação por valor, ferramenta e contexto da delegação.

## Observabilidade e execução segura

O ciclo 11 adiciona `agent_runs`, um trace operacional sem prompt e sem raciocínio interno. Cada execução registra versão, modo, impressão da solicitação, ferramentas planejadas, concluídas e bloqueadas, métricas, limites e erro padronizado.

Os modos oficiais são:

- `live`: permite ações autorizadas e mantém aprovação humana para risco elevado;
- `shadow`: consulta o modelo e registra o que ele tentaria fazer, sem alterar dados;
- `simulation`: executa o mesmo contrato seguro do modo sombra para testes automatizados.

O runtime interrompe o provedor ao atingir `max_runtime_seconds`, bloqueia chamadas além de `max_steps` e vincula ferramentas e consumo ao trace e à versão exata. Os endpoints `GET /agents/{agent_id}/runs` e `GET /agents/{agent_id}/runs/{run_id}` aplicam isolamento por empresa.

O ciclo 65 detalha esse contrato em `agent_run_steps`. Cada execução passa a registrar uma etapa do provedor e uma etapa por ferramenta planejada, com estado, código operacional, duração e fingerprints HMAC vinculados à empresa e à execução. O trace não guarda prompt, resposta completa, argumentos, resultados, credenciais nem raciocínio interno. Execuções diretas, simulações e delegações multiagentes usam o mesmo contrato. A consulta `GET /agents/{agent_id}/runs/{run_id}/steps` exige `agents.view` e filtra simultaneamente agente, execução e `company_id`.

## Política de dados e defesa contra prompt injection

O ciclo 12 adiciona uma política individual por agente. Ela define provedores permitidos, autorização para processamento externo, envio de mensagens e conhecimento, classificação máxima e mascaramento obrigatório. O endpoint administrativo é `GET/PUT /agents/{agent_id}/data-policy`.

Antes de chamar um provedor externo, o runtime valida a política e mascara e-mails, CPF, CNPJ, bearer tokens e atribuições comuns de senha, token ou chave. Provedores não autorizados são bloqueados antes de qualquer saída.

Mensagens e trechos de conhecimento são examinados por regras determinísticas contra sobrescrita de políticas, exposição do prompt do sistema, exfiltração de segredos e personificação do sistema. Conteúdo suspeito não chega ao modelo. A ocorrência gera `agent_security_events` contendo somente fingerprint SHA-256 e nomes dos indicadores. O endpoint `GET /agents/{agent_id}/security-events` respeita `company_id` e `agents.configure`.

## Avaliação e bloqueio de publicação

O ciclo 13 adiciona suítes vinculadas a uma versão em rascunho. Cada caso sintético declara se deve ser bloqueado, ferramentas esperadas e ferramentas proibidas. A execução é determinística, não chama provedor pago e gera resultados versionados com códigos de falha.

Quando `require_evaluation_for_publish=true`, uma versão somente pode ser publicada após uma execução com pontuação igual ou superior ao mínimo da suíte. O bootstrap inicial cria a versão 1 publicada; toda evolução posterior passa pelo gate.

- `POST /agents/{agent_id}/versions/{version_id}/evaluation-suites`
- `POST /agents/{agent_id}/versions/{version_id}/evaluation-suites/{suite_id}/run`

## Coordenação multiagente

O ciclo 14 introduz contratos de tarefa entre um supervisor de autonomia nível 4 e agentes especialistas. O contrato limita ferramentas, contexto, passos, custo, prazo e profundidade de subdelegação. Nenhum contrato pode ampliar os limites da versão publicada do especialista.

Delegações são idempotentes e seguem a máquina de estados `queued`, `in_progress`, `completed`, `failed` ou `cancelled`. Objetivo e resultado são convertidos em fingerprints SHA-256 com escopo da empresa; o texto não é armazenado em contratos, eventos ou respostas.

Handoffs exigem decisão explícita e revalidam o agente de destino contra o contrato original. Contratos, delegações e handoffs geram auditoria e eventos mínimos com `company_id`.

- `GET/POST /agents/{supervisor_id}/task-contracts`
- `POST /agents/{supervisor_id}/delegations`
- `GET /agents/{supervisor_id}/delegations/{delegation_id}`
- `POST /agents/{supervisor_id}/delegations/{delegation_id}/transition`
- `POST /agents/{supervisor_id}/delegations/{delegation_id}/handoffs`
- `POST /agents/{supervisor_id}/delegations/{delegation_id}/handoffs/{handoff_id}/decision`

## Worker de delegações e payload efêmero

O ciclo 15 conecta delegações ao Celery sem colocar objetivos na mensagem Redis. A fila recebe somente o identificador da delegação. O objetivo é protegido com AES-256-GCM, chave derivada do segredo da plataforma e dados associados de empresa e delegação, impedindo cópia de ciphertext entre tenants.

O worker realiza claim transacional com lease, recupera leases vencidos, valida contrato, versão, política de dados, prompt injection, autonomia e ferramentas antes da execução. O custo e os passos permanecem limitados pelo contrato. A execução gera `AgentRun` e evento mínimo.

O ciphertext é destruído quando a tarefa conclui, falha, é cancelada ou expira. A manutenção `orkestral.agents.maintain_delegations` roda a cada minuto para expirar payloads e recuperar trabalhos interrompidos. A tarefa `orkestral.agents.process_delegation` possui retry com backoff e jitter.

## Aprovação humana assíncrona

O ciclo 16 faz o worker pausar uma delegação antes de qualquer ferramenta que exija supervisão. Os argumentos são protegidos por AES-256-GCM com dados associados de empresa, delegação e aprovação. A solicitação entra na central existente de notificações sem argumentos ou objetivo.

Uma aprovação válida move a delegação novamente para `queued`; o worker revalida usuário, permissões, contrato, agente e ferramenta, descriptografa exatamente a chamada aprovada e executa sem consultar novamente o modelo. Rejeição, expiração ou falha destroem objetivo e argumentos cifrados. A decisão é idempotente e isolada por empresa.
A partir do ciclo 17, a decisão também consulta políticas empresariais versionadas por
agente. Cada política publicada pode permitir, exigir aprovação ou bloquear uma
ferramenta por prioridade, faixa de valor em microunidades, moeda e condições exatas
de contexto. Uma regra `allow` nunca remove controles de autonomia ou risco já
existentes; `deny` prevalece em prioridades equivalentes.

As notificações recebem somente identificadores da política, nunca os argumentos da
ferramenta. Antes de retomar uma ação aprovada, o worker reavalia as regras publicadas
e interrompe a execução caso uma política nova seja mais restritiva.

## Ciclo 66 — Agendas, eventos e credenciais governadas

O runtime passa a receber trabalho por agendas e eventos versionados. Antes de liberar um despacho, o worker confirma no limite da empresa que a ferramenta está habilitada e que existe um vínculo com credencial ativa e não expirada. O registro operacional guarda apenas referências seguras e uma impressão HMAC do objetivo; segredos e payloads externos não entram na instrução do agente.

A execução efetiva dos despachos prontos será adicionada no próximo recorte, com política, orçamento, aprovação, modo sombra e trace operacional.
## Executor governado de despachos

Agendas e eventos sao consumidos por um executor fail-closed. O runtime fixa empresa,
versao, responsavel, ferramentas e argumentos, aplica permissao, orcamento, autonomia e
politica de aprovacao, e somente entao permite uma ferramenta real. O padrao e modo sombra;
liberacao real exige `live` e percentual canario explicito. Cada decisao gera auditoria,
evento de dominio e passos operacionais sem expor raciocinio interno ou segredos.

## Ciclo 68 - reconciliacao fail-closed de despachos

O executor reconcilia despachos abandonados em `processing` depois do limite
de duracao do agente e de uma margem operacional. A reconciliacao encerra a
execucao, libera a reserva de custo, grava trace e auditoria e publica
`agent.dispatch.interrupted`. Como o resultado de uma ferramenta externa pode
ser desconhecido apos uma queda, nenhuma repeticao e automatica: a politica
registrada e `manual_review_required`.

A configuracao de agendas e gatilhos expoe modo sombra, execucao real, percentual
canario e argumentos JSON por ferramenta. O navegador bloqueia estruturas
invalidas ou ferramentas nao declaradas, enquanto o backend continua sendo a
autoridade final para autorizacao, politica, empresa e orcamento.

## Ciclo 69 - revisao administrativa e repeticao controlada

Interrupcoes com resultado externo incerto passam por uma decisao persistida e
idempotente. `agents.configure` registra o motivo e decide encerrar ou preparar
uma repeticao; `agents.execute` concede a aprovacao explicita. Somente depois
dessa segunda etapa um novo despacho e criado.

O novo despacho usa `source_type=retry`, referencia o anterior por
`retry_of_dispatch_id` e revalida credenciais. Ele nao herda estado de
processamento, reserva de custo ou execucao anterior. Orcamento, politicas,
aprovacoes por ferramenta, trace e auditoria sao aplicados novamente pelo
executor comum.

## Ciclo 70 - SLA e alertas de revisao

Revisoes pendentes possuem resumo operacional por empresa e agente. O painel
mostra contagens e duracoes sem consultar ou expor argumentos de ferramentas.
Um job idempotente identifica itens acima do SLA, notifica responsaveis e emite
`agent.dispatch.review_sla_breached` apenas uma vez por revisao.
