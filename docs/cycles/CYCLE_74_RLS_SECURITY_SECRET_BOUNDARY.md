# Ciclo 74 - RLS, testes ofensivos e fronteira de segredos

## Objetivo

Adicionar defesa em profundidade ao isolamento multiempresa e impedir que
segredos de infraestrutura sejam enviados ao navegador.

## Entrega

- RLS forcado para todas as tabelas empresariais atuais;
- politica complementar para associacoes que herdam tenant do registro pai;
- papel PostgreSQL operacional e papel somente leitura, ambos sem login;
- contexto transacional reaplicado depois de commit ou rollback;
- `WITH CHECK` contra mass assignment e escrita cruzada;
- testes controlados de IDOR, cabecalho de empresa forjado, SQL injection,
  mass assignment, leitura cruzada direta e escrita somente leitura;
- contrato que proibe campos de segredo nos modelos de resposta da API;
- allowlist fechada das variaveis publicas `VITE_*`;
- token de acesso mantido somente em memoria e refresh token em cookie HttpOnly;
- sonda sintetica que exige falha do build quando uma variavel de segredo e
  prefixada com `VITE_`;
- varredura do bundle compilado por formatos conhecidos de chaves.

## Modelo de ameaca coberto

Os testes simulam erros de autorizacao e entradas hostis somente contra a
instancia local controlada. Eles nao atacam terceiros nem executam destruicao.
RLS reduz o impacto de um filtro de tenant esquecido, enquanto schemas estritos
e SQL parametrizado bloqueiam alteracao de `company_id` e injecao.

## Riscos residuais

- superusuarios e papeis com `BYPASSRLS` ignoram politicas por definicao do
  PostgreSQL;
- migracoes e jobs de sistema ainda usam a credencial administrativa;
- RLS nao protege tabelas globais, que dependem de RBAC e schemas de resposta;
- DAST externo autenticado deve ser executado em um ambiente descartavel antes
  da producao, nunca contra dados reais.

## Validacao executada

- 216 testes unitarios de API e worker aprovados;
- integracoes completas aprovadas, incluindo duas novas sondas RLS;
- 19 testes de interface aprovados;
- 7 jornadas E2E aprovadas e 2 condicionais ignoradas;
- lint integral e tipagem de 224 arquivos produtivos aprovados;
- build de producao aprovado;
- downgrade para `0088` e retorno ao head `0089` aprovados com API e worker
  pausados;
- auditorias de segredos, bundle, Node, Python, Bandit e contratos CI aprovadas.

Alteracoes de politica RLS adquirem locks de schema. Downgrade ou manutencao
deve pausar API e worker, executar a migracao em processo isolado e somente
entao restaurar trafego. A tentativa concorrente foi revertida atomicamente
pelo PostgreSQL ao detectar deadlock, sem deixar alteracao parcial.

## Proximo passo

Separar credenciais de banco para migracao, API e worker, depois adicionar
multiplos turnos e calendarios de feriados ao plantao de agentes.
