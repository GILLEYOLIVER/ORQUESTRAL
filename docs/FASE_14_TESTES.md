# Fase 14 - estrategia de testes

Esta fase transforma os criterios do documento mestre em verificacoes automatizadas e
reproduziveis. A execucao normal do produto nao usa simuladores. O arquivo
`docker-compose.test.yml` existe somente para contratos deterministas durante os testes.

## Estado concluido

A bateria completa foi validada em macOS em 19/07/2026:

| Suite                 | Resultado                         |
| --------------------- | --------------------------------- |
| Backend e worker      | 77 testes aprovados               |
| Frontend              | 9 testes aprovados                |
| PostgreSQL e Redis    | 4 testes de integracao aprovados  |
| Jornada ponta a ponta | 7 testes aprovados                |
| Total                 | 97 testes automatizados aprovados |

As integracoes foram executadas em containers descartaveis com todas as migrations ate
`20260719_0015`. A jornada ponta a ponta validou PostgreSQL, Redis, MinIO, n8n, contratos
externos, isolamento multiempresa e os dez passos obrigatorios. Ao final, os dados temporarios
foram removidos e o ambiente Docker local foi restaurado com todos os servicos saudaveis.

## Matriz de cobertura

| Categoria     | Cobertura automatizada                                                                                                                                                                 |
| ------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Unitarios     | Servicos, regras de negocio, permissoes, validacoes, compilador de workflows, limites e consumo em `apps/api/tests`; componentes, guards e cliente HTTP em `apps/web/src/**/*.test.*`. |
| Integracao    | PostgreSQL e Redis em `tests/integration`; MinIO, n8n real, provedor OpenAI compativel e plugin HTTP na suite `phase14-journey.spec.ts`.                                               |
| Seguranca     | Rotas sem autorizacao, escalonamento de privilegio, IDs entre empresas, campo `company_id` injetado, upload executavel e vazamento de credenciais na jornada da Fase 14.               |
| Ponta a ponta | Empresa, usuario, modulo, plugin, agente, ferramenta, workflow, execucao, logs e consumo pela API publicada no proxy local.                                                            |

## Contratos externos

O servico `phase14-contract` simula apenas as respostas externas de n8n, OpenAI compativel e
HTTP generico. Ele roda em container sem privilegios, somente leitura, sem segredos reais e
nao e carregado por `docker-compose.yml`. O n8n e o MinIO reais continuam ativos, e a saude
de ambos e validada internamente pelo contrato antes de a API iniciar.

## Executar no macOS ou Linux

```bash
bash scripts/test-phase14.sh
```

O script pausa o ambiente local apenas enquanto usa as mesmas portas, cria volumes isolados
com o projeto Compose `orkestral-phase14`, executa a jornada e remove esses volumes. Ao sair,
mesmo em caso de falha, ele restaura o ambiente local que estava em execucao.

## Integracao continua

O job `end-to-end` combina `docker-compose.yml`, `docker-compose.development.yml` e
`docker-compose.test.yml`, alem de definir `PHASE14_E2E=true`. Os demais jobs continuam
executando unitarios, integracao com PostgreSQL e Redis, contratos, lint, tipagem e builds de
containers. A Fase 14 so fica verde quando a jornada completa e todas as verificacoes
anteriores terminam com sucesso.
