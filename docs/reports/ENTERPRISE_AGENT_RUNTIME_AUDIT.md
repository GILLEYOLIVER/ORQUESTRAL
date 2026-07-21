# Auditoria empresarial do runtime de agentes

Data: 21 de julho de 2026.

## Resumo executivo

O Orkestral possui um runtime de agentes basico funcional, classificado como Nivel 2. A base atual ja separa dados por empresa, registra conversas e consumo, oferece ferramentas tipadas, exige permissao por ferramenta e encaminha operacoes sensiveis para aprovacao humana.

Ainda nao e um runtime autonomo empresarial. Faltam versoes publicaveis do agente, politicas independentes, niveis graduados de autonomia, orcamentos preventivos, modo sombra, suites de avaliacao, traces operacionais completos, memoria governada e coordenacao multiagente.

## Inventario confirmado em execucao

### Provedores

| Provedor            | Configurado localmente | Observacao                                                        |
| ------------------- | ---------------------- | ----------------------------------------------------------------- |
| `local`             | Sim                    | Permite testes sem enviar dados a um provedor externo             |
| `openai_compatible` | Nao                    | Contrato existe, mas depende de configuracao e credencial externa |

### Ferramentas registradas

| Chave                           | Risco    | Permissao             |
| ------------------------------- | -------- | --------------------- |
| `orkestral.company.summary`     | Consulta | `agents.execute`      |
| `orkestral.workflow.status`     | Consulta | `workflows.view`      |
| `orkestral.workflow.deactivate` | Sensivel | `workflows.configure` |

### Persistencia existente

| Estrutura             | Funcao atual                                                                       |
| --------------------- | ---------------------------------------------------------------------------------- |
| `agents`              | Configuracao, modelo, instrucoes, limites de tokens, base de conhecimento e status |
| `agent_tools`         | Ferramentas habilitadas, schema de entrada, permissao e sensibilidade              |
| `agent_conversations` | Conversas vinculadas a empresa, agente e usuario                                   |
| `agent_messages`      | Mensagens, chamada de ferramenta, modelo, tokens, custo e duracao                  |
| `agent_tool_runs`     | Estado da operacao, argumentos, resultado, erro e aprovacao humana                 |
| `agent_usage_records` | Consumo por empresa, agente, conversa, modelo e ferramenta                         |

## Capacidades existentes

- CRUD de agentes por empresa.
- Conversas auditaveis e mensagens persistidas.
- Catalogo de ferramentas com JSON Schema de entrada.
- Permissao obrigatoria declarada por ferramenta.
- Marcacao de ferramenta sensivel.
- Solicitacao e decisao de aprovacao humana.
- Registro de resultado real ou erro da ferramenta.
- Uso de modelo local e contrato para modelo compativel externo.
- Associacao opcional com base de conhecimento.
- Medicao de tokens, custo em microunidades e duracao.
- Isolamento estrutural por `company_id`.

## Lacunas para nivel empresarial

| Capacidade                     | Estado atual                                  | Risco                                              |
| ------------------------------ | --------------------------------------------- | -------------------------------------------------- |
| `AgentVersion`                 | Configuracao editada no mesmo registro        | Alteracao sem rollback confiavel                   |
| Politicas versionadas          | Regras distribuidas no codigo e na ferramenta | Dificuldade de auditoria e promocao                |
| Niveis de autonomia            | Aprovacao binaria por sensibilidade           | Privilegio excessivo ou operacao travada           |
| Orcamento preventivo           | Consumo e registrado depois                   | Estouro de custo antes do bloqueio                 |
| Limite de passos e tempo       | Parcial                                       | Loops, latencia e consumo descontrolado            |
| Modo simulacao/sombra          | Ausente                                       | Risco ao validar agentes com dados reais           |
| Suites de avaliacao            | Ausente                                       | Regressoes nao detectadas antes da publicacao      |
| Trace operacional              | Parcial                                       | Investigacao incompleta de decisao e ferramenta    |
| Memoria governada              | Conversa e mensagens basicas                  | Retencao, consentimento e exclusao insuficientes   |
| Citacoes RAG                   | Busca existe, contrato incompleto             | Respostas sem evidencia visivel                    |
| Multiagentes                   | Ausente                                       | Sem delegacao, consolidacao ou supervisor          |
| Politica de dados por provedor | Ausente                                       | Dados podem sair sem classificacao granular futura |

## Modelo-alvo incremental

Primeiro conjunto de estruturas:

- `AgentVersion`: snapshot imutavel e publicavel da configuracao.
- `AgentPolicy`: autonomia, dados, ferramentas, horarios, limites e aprovacao.
- `AgentBudget`: limite por execucao, dia, mes, equipe e agente.
- `AgentRun`: objetivo, versao, origem, estado, custo e conclusao.
- `AgentStep`: plano operacional resumido e estado de cada passo.
- `AgentEvaluationSuite` e `AgentEvaluationCase`: entradas, acoes esperadas e proibidas.
- `AgentMetric`: sucesso, transferencia humana, custo, latencia e violacao.
- `AgentMemory`: escopo, classificacao, expiracao, consentimento e eliminacao.

## Fluxo-alvo de execucao

1. Autenticar origem e resolver empresa.
2. Resolver usuario, canal e versao publicada.
3. Carregar permissoes, politica e orcamento.
4. Classificar intencao e recuperar somente contexto autorizado.
5. Criar plano operacional resumido com limite de passos.
6. Selecionar ferramentas registradas e validar schemas.
7. Avaliar risco por acao, registro e campo.
8. Simular ou solicitar aprovacao quando exigido.
9. Executar com timeout, idempotencia e limite de custo.
10. Validar o resultado real antes de responder.
11. Registrar auditoria, metricas e memoria permitida.
12. Concluir, transferir para humano ou falhar de forma explicita.

## Controles de seguranca prioritarios

- Nenhuma ferramenta acessa banco diretamente fora dos servicos autorizados.
- Argumentos e resultados devem possuir schemas versionados.
- Instrucoes encontradas em documentos nao substituem politicas do sistema.
- Contexto, memoria, conhecimento e credenciais nunca atravessam empresas.
- Ferramentas financeiras, destrutivas ou externas exigem politica e aprovacao.
- Segredos nunca entram em prompt, mensagem persistida, trace ou resposta.
- Toda execucao recebe limite de passos, tempo, chamadas externas e custo.
- Falha de ferramenta nunca pode ser apresentada como sucesso.

## Primeiro recorte recomendado

Implementar `AgentVersion`, `AgentPolicy` e `AgentBudget` de ponta a ponta. O recorte deve incluir migracao, publicacao, simulacao somente leitura, enforcement antes da ferramenta, auditoria, API administrativa, interface e testes de acesso entre empresas.

## Criterios de aceitacao do recorte

- Um agente publicado sempre aponta para uma versao imutavel.
- Editar um rascunho nao altera execucoes publicadas.
- Autonomia pode variar por agente e ferramenta.
- Limite de custo bloqueia antes da chamada externa.
- Ferramenta proibida nao e enviada ao modelo.
- Simulacao nao persiste efeitos empresariais.
- Empresa A nao le versoes, politicas, orcamentos ou runs da Empresa B.
- Toda decisao de politica gera auditoria sem segredo.
