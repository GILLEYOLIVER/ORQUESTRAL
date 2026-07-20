# Revisão de dependências - 20/07/2026

## Objetivo

Este relatório registra a análise dos pull requests automáticos abertos pelo Dependabot no repositório privado da Orkestral. A regra adotada foi simples: uma atualização só pode avançar quando seus testes relevantes estiverem aprovados e não houver regressão conhecida no build, nos contratos ou nos containers.

## Resultado executivo

- Sete atualizações foram aprovadas e consolidadas na branch `codex/dependencies-user-guide`.
- Três atualizações foram adiadas porque falharam em verificações obrigatórias ou não correspondiam ao runtime fixado pelo projeto.
- Nenhum segredo, credencial ou dado de cliente foi alterado.
- O repositório permaneceu privado durante toda a revisão.
- Os PRs originais do Dependabot podem ser encerrados como substituídos depois que o PR consolidado for mesclado.

## Matriz de decisão

| PR  | Atualização                                    | Decisão  | Evidência                                                                                                                      |
| --- | ---------------------------------------------- | -------- | ------------------------------------------------------------------------------------------------------------------------------ |
| #23 | `docker/setup-buildx-action` 3.12.0 para 4.2.0 | Aprovada | Backend, frontend, contratos, integração, E2E, segurança, deploy remoto e containers aprovados.                                |
| #24 | `pnpm/action-setup` 4.3.0 para 6.0.9           | Aprovada | Todas as verificações obrigatórias aprovadas. Mantém o pnpm 11.7.0 definido pelo projeto.                                      |
| #25 | `actions/setup-node` 5.0.0 para 7.0.0          | Aprovada | Todas as verificações obrigatórias aprovadas com Node 24.                                                                      |
| #26 | `astral-sh/setup-uv` 7.6.0 para 8.3.2          | Aprovada | Backend, contratos, integração e auditorias aprovados.                                                                         |
| #27 | `actions/checkout` 5.0.1 para 7.0.0            | Aprovada | Todas as verificações obrigatórias aprovadas. O conflito de linhas vizinhas foi resolvido preservando as demais versões novas. |
| #28 | Node 24.18 Alpine para Node 26.5 Alpine        | Adiada   | O build falha porque a imagem não disponibiliza `corepack`; containers, deploy remoto e E2E não iniciam.                       |
| #29 | Python 3.13 slim para Python 3.14 slim         | Adiada   | A base muda para 3.14, mas o `uv` baixa e executa CPython 3.13.14; a imagem cresce sem atualizar o runtime real.               |
| #30 | Nginx 1.30.3 Alpine para 1.31.3 Alpine         | Aprovada | Todas as verificações obrigatórias aprovadas, incluindo containers e E2E.                                                      |
| #31 | Grupo de dependências de produção do frontend  | Aprovada | Frontend, contratos, integração, E2E, segurança e containers aprovados.                                                        |
| #32 | Grupo de dependências de desenvolvimento       | Adiada   | TypeScript 7 quebra o ESLint e a geração OpenAPI: erros em `Cjs` e `createKeywordTypeNode`.                                    |

## Atualizações aprovadas

As atualizações aprovadas afetam somente:

- workflows do GitHub Actions;
- `Dockerfile.web`;
- dependências de produção do frontend;
- `pnpm-lock.yaml`.

Elas não alteram regras de negócio, permissões, dados de empresas, migrações ou contratos públicos deliberadamente.

## Atualizações adiadas

### Node 26

O Node 26 não deve ser adotado enquanto o Dockerfile depender do comando `corepack`. A imagem proposta encerra o build com:

```text
/bin/sh: corepack: not found
```

Antes de reavaliar:

1. definir a estratégia oficial de instalação do pnpm na imagem;
2. atualizar os Dockerfiles de forma explícita;
3. construir os containers web e remoto;
4. executar o E2E completo;
5. confirmar compatibilidade com Vite e bibliotecas do frontend.

### Python 3.14

O runtime Python do projeto continua fixado em 3.13.14. Durante a construção com uma imagem base 3.14, o `uv` baixou CPython 3.13.14 e criou o ambiente virtual com essa versão. Portanto, a imagem carregaria dois runtimes e continuaria executando 3.13.

Antes de reavaliar:

1. atualizar de forma consciente a restrição de Python do projeto;
2. regenerar e validar o `uv.lock` para Python 3.14;
3. confirmar suporte de FastAPI, SQLAlchemy, asyncpg, Celery e bibliotecas nativas;
4. executar testes e migrações diretamente em Python 3.14;
5. confirmar que o `uv` não baixa uma segunda versão durante o build;
6. comparar tamanho, segurança e tempo de inicialização da imagem.

### TypeScript 7 e dependências de desenvolvimento

O grupo do PR #32 não deve ser adotado como conjunto. Foram observadas incompatibilidades entre TypeScript 7, `typescript-eslint` e `openapi-typescript`:

```text
Cannot read properties of undefined (reading 'Cjs')
Cannot read properties of undefined (reading 'createKeywordTypeNode')
```

Antes de reavaliar:

1. aguardar versões compatíveis de `typescript-eslint` e `openapi-typescript`;
2. separar o grupo em atualizações menores;
3. executar lint, typecheck e geração de contratos;
4. confirmar que `api.generated.ts` permanece reproduzível;
5. executar frontend, integração e E2E.

## Estratégia de integração

As sete atualizações aprovadas foram consolidadas em uma única branch para evitar mesclar vários PRs sobrepostos diretamente no `main`. Essa estratégia oferece:

- um único ponto de revisão;
- uma única bateria final de testes;
- rollback simples;
- histórico claro;
- menor risco de conflitos entre workflows.

## Checklist antes do merge

- [ ] `pnpm install --frozen-lockfile`
- [ ] formatação, lint e typecheck do frontend
- [ ] testes e build do frontend
- [ ] Ruff, MyPy e testes do backend
- [ ] geração e verificação dos contratos
- [ ] build dos containers atualizados
- [ ] E2E principal
- [ ] confirmação de que o repositório continua privado

## Procedimento depois do merge

1. sincronizar `main` com `development`;
2. acompanhar o deploy nativo do Render;
3. confirmar `/health`, `/ready` e `/system/version`;
4. atualizar o ambiente local;
5. encerrar os PRs #23, #24, #25, #26, #27, #30 e #31 como substituídos;
6. manter #28, #29 e #32 fechados ou adiados com a justificativa técnica acima.

## Rollback

Se uma regressão aparecer depois do merge, reverta o commit de merge do PR consolidado. Não reverta migrações de banco, pois esta atualização não cria nenhuma. Depois do rollback:

1. publique novamente a branch `development`;
2. reconstrua os containers locais;
3. valide health, readiness e a tela inicial;
4. registre a dependência causadora antes de tentar nova atualização.
