# DOCUMENTO MESTRE — FASES 6 A 10

# 11. FASE 6 — INTEGRAÇÃO COM N8N

## Objetivo

Utilizar o n8n como motor interno de execução sem expô-lo ao cliente.

## Serviço central

Crie `modules/workflows/services/n8n_client.py` para autenticação, criação, atualização, ativação, desativação, execução, consulta de status e histórico, timeouts, erros e tentativas controladas.

Nenhuma rota deve chamar o n8n diretamente sem passar por esse cliente.

## Persistência

Crie `workflows` e `workflow_executions` com `company_id`, definição, versão, ID externo, status, datas, resumos de entrada/saída e erro.

## Segurança

Toda execução deve carregar o identificador interno da empresa. Webhooks públicos exigem assinatura, chave ou token, rate limit, validação da empresa e validação do workflow.

## Interface

Crie telas para listar, criar, ativar/desativar, executar manualmente, consultar histórico e erros, duplicar, importar e exportar definições seguras. O cliente não deve ver URLs administrativas nem termos técnicos desnecessários do n8n.

## Critérios de conclusão

- A Orkestral cria e executa um fluxo no n8n.
- O resultado aparece na Orkestral.
- O n8n não é exposto ao usuário final.
- Falhas são registradas e apresentadas de modo compreensível.

---

# 12. FASE 7 — AGENTES DE INTELIGÊNCIA ARTIFICIAL

## Objetivo

Permitir vários agentes por empresa, cada um com função, limites e ferramentas próprias.

## Estrutura

Crie:

```text
agents
agent_tools
agent_conversations
agent_messages
```

Todos os registros de negócio devem possuir `company_id`. Agentes devem guardar instruções, provedor, modelo, temperatura, limites, memória, base de conhecimento, status e criador.

## Abstração de provedores

Crie:

```python
class LanguageModelProvider:
    async def generate(...)
    async def stream(...)
    async def calculate_usage(...)
```

Cada provedor deve viver em um adaptador separado. O agente não pode depender diretamente de uma empresa de IA.

## Ferramentas

A IA não executa código nem altera dados diretamente. O fluxo deve interpretar a solicitação, pedir uma ferramenta, verificar permissão, validar argumentos, executar, devolver o resultado e registrar a operação.

## Ações sensíveis

Exclusões, cobranças, pedidos, cancelamentos, mensagens em massa, alterações financeiras, pagamentos, permissões e automações críticas exigem confirmação.

Estados:

```text
requested
awaiting_confirmation
approved
rejected
executing
completed
failed
```

## Consumo

Registre empresa, usuário, agente, provedor, modelo, tokens, custo, ferramenta, duração e resultado.

## Critérios de conclusão

- Vários agentes por empresa.
- Ferramentas próprias por agente.
- Ferramentas não autorizadas são bloqueadas.
- Tokens e custos são registrados.
- Ações sensíveis exigem confirmação.

---

# 13. FASE 8 — BASE DE CONHECIMENTO

## Objetivo

Permitir que agentes consultem documentos autorizados da empresa.

## Estrutura

Crie:

```text
knowledge_bases
knowledge_documents
knowledge_chunks
```

Inclua empresa, status, armazenamento, checksum, metadados, índice de chunk e referência de embedding.

## Processamento assíncrono

1. Receber o arquivo.
2. Validar tipo e tamanho.
3. Verificar segurança.
4. Armazenar o original.
5. Extrair texto.
6. Dividir em partes.
7. Gerar vetores.
8. Armazenar metadados.
9. Marcar como pronto.
10. Registrar erros.

Suporte inicial: PDF, DOCX, TXT, CSV, XLSX e páginas web autorizadas.

## Consulta

O agente identifica a base permitida, pesquisa apenas documentos da empresa, recupera trechos, consulta o modelo, responde e registra as fontes internas utilizadas.

## Critérios de conclusão

- Processamento ocorre em segundo plano.
- Documentos ficam isolados por empresa.
- Agentes usam somente fontes autorizadas.
- Fontes internas são informadas.
- Documentos podem ser removidos e reprocessados.

---

# 14. FASE 9 — CONSTRUTOR VISUAL DE AUTOMAÇÕES

## Objetivo

Permitir criar fluxos sem acessar o painel do n8n.

## Blocos

Inclua gatilho manual e por horário, webhook, mensagem recebida, novo contato, condição, espera, repetição, consulta, atualização, e-mail, mensagem, agente, aprovação humana, plugin e encerramento.

## Definição neutra

Armazene uma definição própria da Orkestral:

```json
{
  "nodes": [],
  "connections": [],
  "variables": {},
  "version": 1
}
```

Crie um compilador para converter essa definição ao formato do n8n. Não use o formato interno do n8n como única fonte de verdade.

## Validação

Verifique blocos desconectados, ciclos inválidos, credenciais, permissões, campos obrigatórios, ferramentas desativadas, risco de massa e tratamento de erros.

## Versionamento

Implemente rascunho, publicação, histórico, restauração, comparação e duplicação.

## Critérios de conclusão

- Fluxo visual é criado e validado.
- O compilador publica no n8n.
- O histórico de versões é preservado.
- Cada execução pode ser acompanhada.

---

# 15. FASE 10 — DASHBOARDS E RELATÓRIOS

## Objetivo

Apresentar resultados empresariais e operacionais.

## Métricas iniciais

- automações executadas, com sucesso e com falha;
- tempo economizado estimado;
- agentes mais utilizados;
- tokens e custo de IA;
- integrações com falha;
- usuários ativos;
- documentos processados;
- tarefas aguardando aprovação.

Crie um módulo de métricas baseado em eventos internos. Evite consultas pesadas nas tabelas operacionais em cada abertura.

Utilize agregações periódicas, cache, tabelas de resumo e filtros por período, módulo, agente e workflow.

Permita exportação CSV, XLSX e PDF quando apropriado.
