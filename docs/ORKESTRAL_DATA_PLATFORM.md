# Plataforma de dados do Orkestral

## Objetivo

A plataforma de dados cria uma visão canônica e autorizada de pessoas e
organizações sem transformar cada módulo em uma cópia independente do cliente.
PostgreSQL continua como fonte transacional e cada registro permanece isolado
por empresa.

## Primeiro contrato implementado

O perfil 360 reúne:

- contato mestre e cadastros relacionados;
- identidades de e-mail e telefone armazenadas somente como hash e dica
  mascarada;
- fonte e modo de obtenção do dado;
- pontuação e pendências de qualidade;
- consentimentos históricos por finalidade e canal;
- oportunidades abertas;
- atividades comerciais recentes;
- candidatos de duplicidade sem mesclagem automática.

## Resolução de identidade

E-mail é normalizado por caixa e telefone mantém somente dígitos antes do
SHA-256. O valor bruto já existente permanece no sistema de registro CRM; a
camada canônica não cria uma segunda cópia. Uma correspondência inequívoca liga
o novo contato ao perfil existente. Correspondências ambíguas nunca provocam
mesclagem automática.

## Consentimento

Cada decisão é imutável e histórica. Revogar ou negar cria um novo registro,
preservando a trilha. A API registra finalidade, canal, base legal, evidência,
data, responsável e expiração opcional.

## Segurança

Todas as tabelas possuem `company_id`, RLS forçado, políticas restritivas,
permissões separadas de runtime e somente leitura e testes entre empresas. A
interface recebe apenas dicas mascaradas; hashes e valores técnicos de
identidade não fazem parte dos schemas públicos.

## Evolução

Os próximos recortes acrescentarão regras de correspondência versionadas,
decisão humana de fusão e desfusão, linhagem por atributo, ingestão incremental,
qualidade configurável, retenção, anonimização e ativação autorizada.
## Correspondencia e governanca

O Ciclo 78 acrescenta regras versionadas de correspondencia, fila de revisao humana,
fusao reversivel e linhagem de campo por fingerprint. A plataforma nao executa
fusoes automaticamente e nao armazena uma segunda copia do valor sensivel na
trilha de origem.
## Ingestao governada

O Ciclo 79 implementa entrada em lote e incremental com idempotencia, regras
de qualidade versionadas e fila de erros sem persistir a carga sensivel. Os
registros aceitos atualizam o perfil canonico, identidades e linhagem na mesma
transacao.
