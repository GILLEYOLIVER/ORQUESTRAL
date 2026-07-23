# Ciclo 75 - Separacao de identidades PostgreSQL

## Objetivo

Reduzir o impacto de uma credencial comprometida separando as conexoes usadas
por migracoes, API e worker, mantendo RLS como defesa adicional e impedindo que
segredos de infraestrutura atravessem a fronteira do navegador.

## Contrato implementado

- `MIGRATION_DATABASE_URL`: identidade administrativa usada somente por
  Alembic, bootstrap controlado e tarefas de migracao.
- `API_DATABASE_URL`: identidade sem privilegios administrativos usada pela
  API.
- `WORKER_DATABASE_URL`: identidade exclusiva usada pelos workers.
- `DATABASE_PROCESS_ROLE`: seleciona o perfil do processo.
- `DATABASE_ROLE_SEPARATION_REQUIRED`: ativa validacao fail-closed.

Homologacao e producao recusam inicializacao sem as tres URLs, sem TLS, com
usuarios repetidos ou com usuario administrativo na API/worker. Erros de
configuracao ocultam os valores recebidos. Local e desenvolvimento remoto
reduzido preservam `DATABASE_URL` como fallback temporario para nao interromper
o ambiente existente.

## Fronteiras de seguranca

O Alembic sempre seleciona a identidade de migracao. A aplicacao web sempre
seleciona a identidade da API. O container Celery declara o perfil worker. A
checagem de seguranca impede variaveis de banco, Redis, tokens, chaves e
segredos com prefixo `VITE_`.

RLS continua sendo uma defesa contra consultas sem filtro de empresa. Ela nao
substitui parametrizacao SQL, autorizacao na API ou protecao do host. Um invasor
com execucao arbitraria dentro do processo da API deve ser tratado como
incidente critico; a conta sem privilegios limita o alcance, mas nao elimina a
necessidade de rotacao e isolamento da carga.

## Ativacao segura no provedor

1. Criar tres usuarios PostgreSQL independentes no gerenciador do provedor.
2. Conceder ao usuario de migracao somente o necessario para DDL e migracoes.
3. Conceder aos usuarios API e worker acesso ao papel
   `orkestral_tenant_runtime`, sem `SUPERUSER`, `CREATEDB`, `CREATEROLE` ou
   propriedade das tabelas.
4. Armazenar cada URL apenas no cofre de segredos do ambiente.
5. Ativar `DATABASE_ROLE_SEPARATION_REQUIRED=true`.
6. Reiniciar um processo por vez e validar `/ready` sem imprimir URLs.
7. Revogar a credencial compartilhada anterior depois da validacao.

Nunca cole URLs reais em issue, PR, log, screenshot ou arquivo versionado.

## Testes ofensivos

- reutilizacao de usuario entre migracao, API e worker e bloqueada;
- usuario administrativo na API ou worker e bloqueado;
- erro de URL invalida nao revela a senha recebida;
- tentativa de desativar `row_security` durante acesso tenant e bloqueada;
- criacao autorizada de empresa troca o contexto RLS apenas depois da
  permissao de plataforma e cria os papeis dentro do novo tenant;
- respostas autenticadas nao revelam nomes de variaveis de conexao;
- contrato CI verifica que nenhum segredo de infraestrutura usa prefixo Vite.

## Risco residual

O ambiente gratuito atual usa fallback controlado ate que o provedor ofereca
as tres credenciais. Portanto, a separacao de codigo esta concluida, mas a
separacao fisica do ambiente remoto depende do provisionamento protegido no
painel do banco. Producao com clientes nao pode ser promovida com esse fallback.
