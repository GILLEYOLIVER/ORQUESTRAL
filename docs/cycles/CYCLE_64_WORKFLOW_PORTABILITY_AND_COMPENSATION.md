# Ciclo 64 - portabilidade do motor e compensacao por bloco

Data: 22 de julho de 2026.

## Objetivo

Fechar a Fase 3 do plano empresarial removendo chamadas diretas ao n8n do dominio operacional e substituindo a pendencia generica de compensacao por um plano explicito, supervisionado e associado aos blocos que podem causar efeitos.

## Contrato de provider

`WorkflowProvider` define configuracao, health, sincronizacao, ativacao, desativacao, execucao e cancelamento. `N8nWorkflowProvider` implementa esse contrato para o motor atual. `FakeWorkflowProvider` executa o mesmo ciclo de vida sobre a definicao canonica e existe somente como prova deterministica e ambiente de teste.

O workflow passa a guardar `provider_key`, `provider_workflow_id` e `provider_version_id`. Os campos n8n anteriores continuam preenchidos durante a transicao para preservar compatibilidade. Cada execucao registra qual provider foi realmente utilizado.

## Compensacao supervisionada

Uma acao operacional pode declarar:

```json
{
  "compensation": {
    "enabled": true,
    "mode": "manual",
    "action_node_id": "acao-de-reversao"
  }
}
```

O bloco de destino deve ser uma acao com `compensation_only: true`, nao pode participar do caminho normal e nao pode ser compartilhado por duas acoes. Em falha ou cancelamento, a API cria uma lista persistente com os identificadores e rotulos dos blocos. Nenhum argumento operacional ou segredo e copiado para essa lista.

O operador confirma cada item por endpoint especifico. A confirmacao global anterior permanece para execucoes legadas sem itens. Nenhuma compensacao e executada automaticamente.

## Seguranca

- resolucao de workflow e execucao continua filtrada por `company_id`;
- confirmacao exige `workflows.execute`;
- provider e circuit breaker sao separados por empresa;
- payload enviado ao provider falso nao e persistido;
- auditoria contem apenas workflow, execucao e identificador do bloco;
- segredos continuam proibidos na definicao canonica;
- a interface nao afirma que uma reversao ocorreu, somente que o tratamento foi confirmado.

## Migracao

`20260722_0081` adiciona referencias genericas de provider, provider da execucao e o plano JSONB de compensacao. O upgrade copia referencias existentes do n8n e o downgrade remove somente os campos novos.

## Criterios de aceite

- definicao invalida bloqueia alvo ausente, compartilhado ou presente no caminho normal;
- simulacao mostra o plano sem executar efeitos;
- falha ou cancelamento cria itens pendentes;
- confirmacao individual fecha somente o item selecionado;
- provider falso conclui sincronizacao, ativacao, execucao, cancelamento e desativacao;
- n8n continua operando pelo adaptador;
- referencias de tenant e dados empresariais nao atravessam empresas;
- testes, migracao e contratos de interface permanecem aprovados.
