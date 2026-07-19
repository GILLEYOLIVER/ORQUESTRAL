# Compatibilidade do compilador Orkestral para n8n

Compilador `1.1`, validado para n8n a partir de `2.30.6`.

| Bloco Orkestral | Nó n8n | Versão | Estado |
| --- | --- | ---: | --- |
| `trigger.manual` | `manualTrigger` | 1 | suportado |
| `trigger.schedule` | `scheduleTrigger` | 1.2 | suportado |
| `trigger.webhook` | `webhook` | 2 | suportado |
| `trigger.message_received` | `webhook` interno | 2 | suportado |
| `trigger.contact_created` | `webhook` interno | 2 | suportado |
| `logic.condition` | `if` | 2.2 | suportado |
| `logic.wait` | `wait` | 1.1 | suportado |
| `flow.end` | `noOp` terminal intencional | 1 | suportado |
| `logic.loop` | - | - | bloqueado |
| `data.query` | - | - | bloqueado |
| `data.update` | - | - | bloqueado |
| `action.email` | - | - | bloqueado |
| `action.message` | - | - | bloqueado |
| `action.agent` | - | - | bloqueado |
| `action.human_approval` | - | - | bloqueado |
| `action.plugin` | - | - | bloqueado |

O endpoint `GET /api/workflows/blocks/compatibility` é a fonte legível por máquina. A atualização de um workflow existente captura a versão remota anterior e tenta restaurá-la se o n8n recusar o novo payload.
