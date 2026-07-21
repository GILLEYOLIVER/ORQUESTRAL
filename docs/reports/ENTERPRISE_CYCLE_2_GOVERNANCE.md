# Ciclo empresarial 2 - governanca do repositorio e execucao

Data: 21 de julho de 2026.

## Repositorio

- Repositorio oficial: `GILLEYOLIVER/ORQUESTRAL`.
- Visibilidade confirmada: privada.
- Regra permanente: nunca alterar para publico.
- Branch de trabalho deste ciclo: `codex/enterprise-tenancy-cycle-2`.
- Fonte de integracao: pull request para `main`.

## Limitacoes atuais do GitHub

Os jobs do GitHub Actions nao iniciam. A anotacao do proprio GitHub informa falha recente de pagamento ou limite de gastos insuficiente. Como os jobs param antes de obter runner, esse estado nao representa falha dos testes do codigo.

O GitHub tambem recusa branch protection e rulesets neste repositorio privado no plano atual, retornando que o recurso exige GitHub Pro ou repositorio publico. Tornar o repositorio publico e proibido pelo proprietario e nao sera usado como solucao.

Consequencias operacionais:

- o botao de merge nao fica tecnicamente bloqueado por checks;
- `auto-merge` pode mesclar imediatamente quando nao existem checks obrigatorios;
- nenhum novo PR deve ser mesclado automaticamente enquanto os checks remotos estiverem bloqueados;
- a evidencia local deve permanecer registrada, mas nao deve ser apresentada como check remoto aprovado.

## Politica segura de merge

1. Criar branch `codex/*`.
2. Executar a bateria local aplicavel.
3. Fazer commit e push.
4. Abrir pull request privado.
5. Aguardar jobs do GitHub iniciarem e aprovarem.
6. Somente entao mesclar.
7. Se a conta continuar bloqueada, manter o PR aberto e continuar em branch empilhada, sem falsificar aprovacao.

## Ambiente local confirmado no ciclo anterior

| Servico          | Funcao                                     |
| ---------------- | ------------------------------------------ |
| `nginx`          | Entrada HTTP local e proxy reverso         |
| `web`            | Interface React e TypeScript               |
| `api`            | API FastAPI e regras empresariais          |
| `worker`         | Tarefas assincronas Celery                 |
| `postgres`       | Persistencia transacional                  |
| `redis`          | Cache, sessoes e filas                     |
| `n8n`            | Provedor interno de execucao de automacoes |
| `object-storage` | Arquivos compativeis com S3                |

Os oito servicos estavam saudaveis, `/health`, `/ready` e `/app` responderam, e o banco alcancou o head Alembic `20260720_0027` na linha de base.

## Verificacoes locais da linha de base

- Ruff: aprovado.
- MyPy: aprovado em 187 arquivos.
- Pytest unitario: 91 aprovados.
- Pytest de integracao: 5 aprovados.
- Vitest: 9 aprovados.
- Lint, tipos e build do frontend: aprovados.
- Playwright: 5 aprovados e 2 ignorados por contrato de ambiente.
- Auditoria de seguranca: aprovada.
- Migracao `base -> head -> base -> head`: aprovada em banco temporario.

## Recursos financeiros

Nenhum recurso pago foi criado ou habilitado neste ciclo. A correcao da conta do GitHub e uma acao administrativa externa; nao sera contornada tornando o codigo publico.

## Verificacoes locais deste ciclo

- Ruff format: 226 arquivos aprovados apos normalizar dois arquivos do SDK ja presentes em `main`.
- Ruff lint: aprovado.
- MyPy: 165 arquivos de producao aprovados; os dois novos testes tambem foram aprovados isoladamente.
- Pytest unitario: 95 aprovados.
- Pytest de integracao: 6 aprovados.
- Vitest: 9 aprovados.
- ESLint e TypeScript: aprovados.
- Build de producao: aprovado com `VITE_AUTH_PREVIEW_ENABLED=false`, mantendo o acesso rapido restrito ao desenvolvimento local.
- Playwright: 5 aprovados e 2 ignorados por dependerem do ambiente contratual completo.
- Auditoria de seguranca: nenhuma vulnerabilidade conhecida ou segredo real encontrado.
- Containers: 8 de 8 saudaveis.
- HTTP: `/health`, `/ready` e `/app` aprovados.
- Alembic: banco e codigo em `20260720_0027 (head)`.
