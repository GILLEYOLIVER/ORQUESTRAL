# Diagnostico do ambiente remoto

Verificacao executada em **19 de julho de 2026** antes do provisionamento. Este
relatorio registra como o ambiente Docker local foi reduzido sem alterar as
regras de negocio nem remover componentes da arquitetura principal.

## Inventario dos servicos existentes

| Servico | Processo | Dependencias | Porta interna | Persistencia | Uso no remoto inicial |
|---|---|---|---:|---|---|
| `nginx` | proxy de entrada local | web e API | 80 | nenhuma | substituido pelo HTTPS do Render |
| `web` | React/Vite | API | 5173/8080 | nenhuma | compilado e servido no mesmo container da API |
| `api` | FastAPI/Uvicorn | PostgreSQL e Redis | 8000 ou `$PORT` | nenhuma | obrigatorio |
| `worker` | tarefas assincronas | API, PostgreSQL e Redis | - | nenhuma | desativado |
| `postgres` | PostgreSQL | - | 5432 | volume de dados | substituido por Neon externo |
| `redis` | Redis | - | 6379 | volume de dados local | substituido por Upstash externo |
| `n8n` | automacoes | PostgreSQL e rede | 5678 | volume de configuracao | desativado |
| `object-storage` | MinIO/S3 local | - | 9000/9001 | volume de objetos | desativado |

Os health checks, o bootstrap e as migracoes permanecem controlados pelos
arquivos Docker e scripts do repositorio. O container remoto nao depende de
caminhos do computador do desenvolvedor nem grava dados permanentes no seu
sistema de arquivos efemero.

## Classificacao de dependencias

| Necessidade | Servicos |
|---|---|
| Abrir interface | web e API |
| Autenticacao e isolamento multiempresa | API e PostgreSQL |
| Sessoes, limitacao de requisicoes e filas internas | Redis |
| Automacoes reais | n8n e worker |
| Documentos e uploads | armazenamento S3 |
| E-mail transacional | provedor de e-mail e worker |

No primeiro ambiente remoto, somente web, API, PostgreSQL e Redis sao
obrigatorios. n8n, worker, armazenamento de objetos e entrega de e-mail
continuam na arquitetura, mas ficam explicitamente desativados por flags.

## Compatibilidade confirmada

- A API inicia com um unico entrypoint e respeita `PORT` e `0.0.0.0`.
- O frontend gera arquivos estaticos e recebe configuracao `VITE_*` no build.
- PostgreSQL e Redis podem ser externos e usam protocolos padrao.
- A API inicia com n8n, worker, S3 e e-mail desativados.
- `/health`, `/ready`, `/system/version` e `/robots.txt` funcionam sem revelar
  segredos.
- O Docker Compose local permanece como forma oficial de desenvolvimento local.

## Riscos e tratamento

| Risco | Impacto | Controle |
|---|---|---|
| Suspensao por inatividade | primeira requisicao lenta | mensagem amigavel e timeout remoto |
| Disco efemero | perda de arquivos locais | PostgreSQL e Redis externos; uploads desativados |
| Limite de 512 MB | reinicio do servico | container reduzido e worker separado/desativado |
| Banco ou Redis indisponivel | `/ready` falha | health check e logs do provedor |
| Segredo inseguro | comprometimento de dados | validacao no startup e secrets do provedor |
| URL local no remoto | interface inacessivel | contrato automatizado no CI |
| Excesso de cota | suspensao | recursos Free sem cartao e procedimento de desligamento |
| Dados reais em teste | incidente de privacidade | seed ficticio e proibicao documental |

## Conclusao do diagnostico

O modo reduzido e tecnicamente compativel com o projeto. Nenhum servico pago e
necessario, mas o ambiente deve ser tratado somente como desenvolvimento: pode
dormir, iniciar lentamente e ficar indisponivel quando uma cota gratuita for
atingida.
