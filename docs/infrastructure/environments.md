# Ambientes

| Propriedade          | local                  | testing                  | development                  | staging                     | production                  |
| -------------------- | ---------------------- | ------------------------ | ---------------------------- | --------------------------- | --------------------------- |
| Objetivo             | Desenvolvimento no Mac | Validação efêmera de CI  | Demonstração remota gratuita | Homologação pré-lançamento  | Clientes e dados reais      |
| Runtime              | Docker Compose         | GitHub Actions           | Render Web Service único     | Infraestrutura dimensionada | Infraestrutura dimensionada |
| Banco                | PostgreSQL local       | PostgreSQL descartável   | Neon Free                    | Banco isolado               | Serviço gerenciado com SLA  |
| Redis                | Container local        | Redis descartável        | Upstash Free                 | Redis isolado               | Redis gerenciado            |
| n8n/storage/worker   | Ativos                 | Contratos simulados      | Desativados                  | Conforme homologação        | Ativos conforme arquitetura |
| Atalho administrador | Visível                | Proibido                 | Proibido                     | Proibido                    | Proibido                    |
| Dados                | Desenvolvimento        | Fictícios e descartáveis | Somente teste                | Fictícios                   | Reais                       |

O ambiente é definido por `APP_ENV`; o modo remoto exige também `REMOTE_DEVELOPMENT_ENABLED=true`. Nunca copie `.env` entre ambientes. Use `.env.example` localmente e `.env.development.example` apenas como contrato de configuração.

Os contratos `.env.testing.example`, `.env.staging.example` e `.env.production.example` não contêm credenciais utilizáveis. Valores reais pertencem exclusivamente ao secret manager do ambiente.
