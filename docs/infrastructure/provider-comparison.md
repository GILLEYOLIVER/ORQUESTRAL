# Comparacao oficial de provedores gratuitos

Pesquisa refeita em **19 de julho de 2026**, exclusivamente em documentacao
oficial. Planos mudam; os limites devem ser reconfirmados antes de recriar
qualquer recurso.

## Matriz de decisao

| Provedor         | Gratuidade e validade                                                                   | Cartao                                            | Memoria/CPU/armazenamento                                       | Banco/Redis/container                                           | GitHub, HTTPS e dominio                               | Suspensao e trafego                                                    | Risco de cobranca                                          | FastAPI/React e migracao                                               |
| ---------------- | --------------------------------------------------------------------------------------- | ------------------------------------------------- | --------------------------------------------------------------- | --------------------------------------------------------------- | ----------------------------------------------------- | ---------------------------------------------------------------------- | ---------------------------------------------------------- | ---------------------------------------------------------------------- |
| Render           | Web Service Free permanente enquanto respeita as cotas; 750 horas mensais por workspace | nao e necessario para Free                        | 512 MB; CPU compartilhada; disco efemero                        | container web; Postgres Free expira em 30 dias e nao sera usado | deploy Git, TLS e subdominio `onrender.com`           | dorme apos 15 min; largura de banda limitada pelo plano                | baixo sem metodo de pagamento; suspende ao atingir limites | FastAPI via Docker; React estatico no mesmo container; Docker portavel |
| Koyeb            | uma Free Instance por organizacao                                                       | pode exigir verificacao de conta; nao selecionado | 512 MB, 0,1 vCPU e 2 GB SSD sem volume persistente              | um Web Service; nao aceita Worker Free                          | GitHub, HTTPS e dominio Koyeb                         | escala a zero apos 1 h sem trafego                                     | baixo no recurso Free, mas confirmar a tela final          | FastAPI compativel; React estatico; Docker portavel                    |
| Railway          | plano Free de US$ 0 com US$ 1 de credito mensal; trial inicial separado                 | plano pos-pago exige cartao                       | consumo medido; US$ 1 e insuficiente para garantir toda a pilha | containers e servicos gerenciados                               | GitHub, HTTPS e dominio Railway                       | workload para quando acaba credito                                     | maior; modelo de uso e planos pagos usam cobranca pos-paga | tecnicamente compativel, descartado pela previsibilidade financeira    |
| Cloudflare Pages | Free sem prazo, 500 builds/mes                                                          | nao para Pages Free                               | site estatico; 20 mil arquivos, 25 MiB por arquivo              | nao executa o container FastAPI; Functions usam Workers         | Git, HTTPS, `pages.dev`, ate 100 dominios por projeto | CDN; Functions seguem cotas de Workers                                 | baixo no Free sem upgrade                                  | excelente para React; inadequado para a API atual sem reescrita        |
| Neon             | PostgreSQL Free por US$ 0/mes                                                           | nao para Free                                     | 0,5 GB/projeto e 100 CU-h/mes                                   | PostgreSQL padrao                                               | conexao TLS; nao hospeda frontend                     | scale-to-zero em 5 min; 5 GB de egress/mes; suspende ao atingir limite | baixo: suspende no limite Free                             | conexao PostgreSQL portavel e compativel com FastAPI                   |
| Upstash          | um Redis Free; 256 MB e 500 mil comandos/mes                                            | nao para Free; inserir cartao faz upgrade         | 256 MB; ate 10 GB de banda no quadro Free                       | Redis com TLS/REST                                              | nao hospeda aplicacao                                 | aplica limites do plano                                                | baixo enquanto permanecer Free e sem cartao                | protocolo Redis; migracao para outro Redis exige somente trocar URL    |

## Decisao

### Opcao principal

**Render Free + Neon Free + Upstash Free**.

- Custo inicial e mensalidade obrigatoria: **US$ 0**.
- Um container reduzido publica React e FastAPI no mesmo dominio.
- Neon evita o PostgreSQL do Render que expira em 30 dias.
- Upstash fornece Redis persistente sem manter outro container ativo.
- n8n, worker, S3 e e-mail permanecem desativados neste ambiente.
- Desligamento: suspender/excluir o Web Service e excluir os bancos gratuitos.

### Alternativa

**Koyeb Free + Neon Free + Upstash Free**. E portavel, mas a instancia unica de
0,1 vCPU, a restricao a Web Service e a suspensao apos uma hora tornam a
operacao menos simples para demonstracoes.

### Alternativas rejeitadas

- Render PostgreSQL Free: expira em 30 dias e nao oferece backup.
- Railway: o credito mensal nao garante a pilha e o caminho pago e pos-pago.
- Cloudflare Workers/D1 para API: exigiria trocar FastAPI/PostgreSQL e criaria
  aprisionamento desnecessario.

## Fontes oficiais

- [Render Free](https://render.com/docs/free)
- [Koyeb Instances](https://www.koyeb.com/docs/reference/instances)
- [Railway Plans](https://docs.railway.com/pricing/plans)
- [Cloudflare Pages Limits](https://developers.cloudflare.com/pages/platform/limits/)
- [Neon Plans](https://neon.com/docs/introduction/plans)
- [Upstash Redis Pricing](https://upstash.com/pricing/redis)
