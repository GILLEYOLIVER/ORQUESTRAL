# Ciclo 99 - Governança de contato de marketing

## Entregas

1. Consentimento aplicável por canal e validade.
2. Limites móveis de frequência diária e semanal.
3. Dias, horários e fuso permitidos por empresa e canal.

Todo conector deve reservar uma tentativa em `POST /marketing/governance/preflight`.
A reserva é idempotente e serializada por empresa, contato e canal. O backend
bloqueia política ausente, contato de outra empresa, consentimento inválido,
restrição ativa, horário proibido e limite excedido.

As decisões não armazenam conteúdo de mensagens. As novas tabelas possuem RLS
habilitada e forçada.

Próximo ciclo: canais por adaptadores, conteúdo versionado com revisão, landing
pages e formulários.
