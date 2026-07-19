# Ambientes

| Propriedade | local | development | production |
| --- | --- | --- | --- |
| Objetivo | Desenvolvimento completo no Mac | Demonstração/teste remoto gratuito | Clientes e dados reais |
| Runtime | Docker Compose | Render Web Service único | Infraestrutura dimensionada |
| Banco | PostgreSQL local | Neon Free | Serviço gerenciado com SLA |
| Redis | Container local | Upstash Free | Redis gerenciado |
| n8n/storage/worker | Ativos | Desativados | Ativos conforme arquitetura |
| Atalho administrador | Visível | Proibido | Proibido |
| Dados | Desenvolvimento | Somente teste | Reais |

O ambiente é definido por `APP_ENV`; o modo remoto exige também `REMOTE_DEVELOPMENT_ENABLED=true`. Nunca copie `.env` entre ambientes. Use `.env.example` localmente e `.env.development.example` apenas como contrato de configuração.
