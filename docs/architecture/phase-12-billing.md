# Fase 12 - Planos, assinaturas e limites

## Decisões

- Planos são globais e administrados apenas por administradores da plataforma.
- Assinaturas pertencem a uma empresa e preservam o período contratado e o histórico de cancelamento.
- A tabela `usage_records` funciona como ledger idempotente para eventos medidos e integrações externas.
- Contagens de recursos usam as tabelas operacionais como fonte de verdade para não perder dados anteriores à Fase 12.
- Tokens e execuções são avaliados no período da assinatura; usuários, agentes, automações, integrações, documentos e armazenamento usam o estado atual.
- Chaves ausentes no objeto `limits` significam capacidade ilimitada. Valores zero ou negativos são rejeitados.
- Nenhum plano ou preço é criado automaticamente pela migração.

## Fiscalização

`BILLING_ENFORCEMENT_ENABLED=false` mantém o ambiente local utilizável enquanto o catálogo comercial é configurado. Em produção a configuração central exige explicitamente `true`.

Quando a fiscalização está ativa:

- empresa sem assinatura ativa recebe HTTP 402;
- consumo projetado acima do plano recebe HTTP 402 com mensagem empresarial;
- a verificação ocorre no back-end antes da operação;
- a assinatura corrente é bloqueada durante a verificação para reduzir disputas concorrentes.

## Recursos medidos

| Métrica         | Fonte de verdade                         |
| --------------- | ---------------------------------------- |
| Usuários        | vínculos ativos ou convidados da empresa |
| Agentes         | agentes ativos                           |
| Automações      | workflows cadastrados                    |
| Execuções       | execuções no período corrente            |
| Tokens          | consumo de agentes no período corrente   |
| Armazenamento   | soma dos documentos armazenados          |
| Integrações     | plugins ativos da empresa                |
| Documentos      | documentos da base de conhecimento       |
| Chamadas de API | registros idempotentes de consumo        |

## Operação

1. O administrador cria planos em **Plano e consumo**.
2. O administrador atribui um plano ativo a uma empresa.
3. A empresa acompanha consumo, saldo e renovação na mesma área.
4. Um provedor de pagamento poderá futuramente atualizar os estados `past_due`, `cancelled` e `expired` sem alterar o serviço de limites.
