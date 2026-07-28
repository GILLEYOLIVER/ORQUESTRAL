# Ciclo 103 - Pedidos, reservas, contratos e receita

Data: 28 de julho de 2026.

## Entrega

- pedido idempotente criado exclusivamente a partir de proposta aceita;
- itens e valores copiados como snapshots imutáveis;
- reserva de estoque protegida por bloqueio de linha e saldo disponível;
- confirmação atômica que consome a reserva, baixa estoque e cria conta a receber;
- contrato opcional ligado ao pedido;
- assinatura comercial mensal ou anual separada do billing SaaS do Orkestral;
- auditoria e eventos transacionais para criação e confirmação;
- RLS forçado em pedidos, itens, reservas, contratos e assinaturas.

O navegador nunca informa preço final nem saldo resultante. Esses valores são
obtidos e validados no backend dentro da empresa corrente.
