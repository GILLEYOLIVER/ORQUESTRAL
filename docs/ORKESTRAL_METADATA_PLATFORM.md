# Plataforma de Metadados do Orkestral

Atualizado em: 21 de julho de 2026.

## Objetivo

O Orkestral Studio permite que cada empresa modele registros proprios sem alterar o nucleo. Definicoes, dados, configuracoes visuais e regras permanecem isolados por `company_id` e vinculados a uma versao imutavel depois da publicacao.

## Contratos implementados

- entidade e campos tipados;
- versoes em rascunho, validada, publicada e retirada;
- registros personalizados com idempotencia e concorrencia otimista;
- layouts com secoes e ordem dos campos;
- visualizacoes com colunas, filtros e ordenacao declarativos;
- regras de validacao deterministas;
- relacionamentos tipados `many_to_one` e `one_to_one` com integridade tenant-scoped;
- formulas declarativas com operadores permitidos e deteccao de ciclos;
- tipos de registro associados a layouts condicionais;
- formulario e lista renderizados no Orkestral Studio;
- Policy Engine, auditoria e transactional outbox.

## Ciclo de vida

1. O administrador cria ou abre uma entidade.
2. Campos, layout, lista e regras sao salvos no rascunho.
3. A API valida referencias, duplicidades, defaults e operadores.
4. A publicacao torna a versao imutavel.
5. Registros passam a usar o schema e as regras publicados.
6. Uma evolucao cria nova versao copiando a configuracao anterior.

## Endpoints

- `GET /metadata/entities/{id}/design`: consulta o design da versao atual.
- `PUT /metadata/entities/{id}/design`: substitui o design do rascunho.
- `POST /metadata/entities/{id}/validate`: valida campos e design.
- `POST /metadata/entities/{id}/publish`: publica a versao validada.

## Seguranca

- todas as consultas filtram empresa e versao;
- outra empresa recebe `404`, sem confirmar a existencia do recurso;
- somente rascunhos podem ser alterados;
- regras nao executam Python, JavaScript, SQL ou chamadas externas;
- valores dos registros nao entram nos eventos de configuracao;
- regras tambem sao aplicadas no back-end, independentemente da interface;
- campos calculados recusam escrita manual e nunca executam codigo;
- referencias sao resolvidas somente dentro da empresa e bloqueiam exclusao do alvo em uso;
- publicacao exige permissao dedicada e avaliacao de risco.

## Operadores permitidos

- igual e diferente;
- maior e menor para valores numericos normalizados;
- contem para texto e colecoes;
- vazio e nao vazio.

## Operadores de formula permitidos

- soma, subtracao, multiplicacao e divisao decimal segura;
- concatenacao de texto;
- primeiro valor preenchido;
- operandos limitados a campos declarados ou literais validados.

## Lacunas seguintes

- multiplas visualizacoes escolhidas pelo usuario;
- filtros salvos executados no repositorio com paginacao segura;
- importacao, exportacao e empacotamento de metadados.

## Ciclo 55 - visualizacoes operacionais e portabilidade

O Studio passa a operar multiplas visualizacoes versionadas por entidade. Cada visualizacao
define colunas, filtros e ordenacao com operadores permitidos por tipo de campo. A API aplica
essas definicoes somente sobre a versao publicada, com SQL parametrizado, paginacao no servidor
e bloqueio quando um filtro tenta usar campo que o usuario nao pode consultar.

Entidades tambem podem ser exportadas como pacotes `1.0` e importadas em outra empresa ou
ambiente. O pacote inclui schema, layouts, visualizacoes, validacoes, formulas, tipos de registro
e relacionamentos por chave tecnica. Ele nao inclui registros, `company_id`, credenciais ou IDs
internos. Um checksum SHA-256 detecta alteracoes antes da importacao.

Limites conscientes deste ciclo:

- a importacao cria uma nova entidade em rascunho; atualizacao ou mesclagem ficam para pacotes
  versionados do marketplace;
- destinos externos de relacionamentos devem existir na empresa receptora;
- filtros livres enviados pelo cliente nao sao aceitos: somente visualizacoes publicadas podem
  controlar a consulta.
