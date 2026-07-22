# Ciclo 65 — Trace operacional seguro de agentes

## Objetivo

Transformar o resumo agregado de `AgentRun` em uma trilha operacional compreensível, persistente e segura para execuções diretas e multiagentes.

## Entrega

- nova tabela `agent_run_steps`, isolada por empresa e vinculada à execução;
- etapa do provedor e etapas individuais de ferramenta;
- estados de execução, simulação, bloqueio, aprovação, falha e timeout;
- fingerprints HMAC com domínio de empresa, execução e sequência;
- ausência deliberada de prompts, argumentos, respostas completas, segredos e raciocínio interno;
- API de leitura protegida por `agents.view` e `company_id`;
- painel visual responsivo na área de agentes;
- instrumentação do chat, modo sombra, simulação e delegações;
- migração Alembic reversível `20260722_0082`.

## Segurança

O trace armazena somente metadados operacionais permitidos. Valores de entrada e saída são convertidos em HMAC-SHA256 antes da persistência. O segredo utilizado não aparece na resposta e fingerprints de empresas diferentes nunca coincidem para o mesmo conteúdo.

## Critérios de aceite

- uma execução concluída possui etapa do provedor;
- cada ferramenta planejada possui estado individual;
- ações aguardando aprovação permanecem visíveis sem seus argumentos;
- bloqueios e timeouts apresentam códigos seguros;
- nenhuma empresa consulta passos de outra empresa;
- a interface não apresenta raciocínio interno do modelo.
