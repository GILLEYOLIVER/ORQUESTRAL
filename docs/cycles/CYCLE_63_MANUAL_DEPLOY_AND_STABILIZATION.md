# Ciclo 63 - Deploy manual e estabilizacao

Data: 22/07/2026

## Decisao

O ambiente remoto de desenvolvimento nao realiza mais deploy por push, merge, conclusao de CI ou
qualquer outro gatilho automatico. A publicacao exige um SHA completo da branch `development`, uma
acao humana explicita e verificacao posterior da versao e da prontidao.

## Implementacao

- `render.yaml` define `autoDeployTrigger: off`;
- o workflow de desenvolvimento aceita somente `workflow_dispatch` com `release_sha`;
- o deploy hook recebe `ref=SHA`, o que tambem desliga Auto-Deploy no servico existente;
- o script manual valida origem, branch e formato do SHA sem imprimir o hook;
- os contratos CI/CD recusam a reintroducao de `workflow_run` e Auto-Deploy;
- a documentacao diferencia claramente push, merge, deploy e verificacao.

## Estabilizacao

- circuitos novos recebem `state=closed` e `failure_count=0` no proprio dominio, sem depender da
  materializacao tardia dos defaults do banco;
- o teste do monitor usa uma sessao isolada e nao tenta acessar um PostgreSQL externo;
- nenhuma credencial, volume ou dado local foi alterado.

## Operacao

1. Mesclar em `main` e sincronizar `development`.
2. Executar as verificacoes locais.
3. Escolher o SHA completo de `origin/development`.
4. Iniciar o deploy manual no Render ou pelo script protegido.
5. Confirmar `/system/version` e `/ready`.
6. Em falha, manter a release anterior e investigar antes de nova tentativa.

## Seguranca

O deploy hook e um segredo com poder operacional. Ele nao pode ser versionado, exibido, enviado em
argumento, persistido em arquivo ou reutilizado fora do ambiente de desenvolvimento.
