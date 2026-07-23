# Ciclo 87 — direitos do titular

## Entrega

O ciclo completa o núcleo operacional de privacidade da plataforma de dados:

- pacote portátil de acesso em JSON;
- correção governada dos dados canônicos;
- restrição e liberação do processamento automatizado;
- auditoria sem valores pessoais;
- RLS nas novas tabelas;
- permissão específica de exportação;
- bloqueio de ingestões e sincronizações de perfis restritos;
- interface administrativa responsiva.

## Segurança

- o pacote é produzido sob demanda e recebe `Cache-Control: no-store`;
- o front-end usa um `Blob` temporário e revoga imediatamente a URL;
- hashes internos de identidade não fazem parte do pacote;
- a auditoria registra apenas identificadores internos e nomes de campos;
- correções não são armazenadas como texto em solicitações ou eventos;
- restrições são aplicadas com lock transacional por empresa e perfil;
- todas as consultas usam `company_id` e as tabelas usam RLS forçada.

## Contratos

- `POST /crm/customer-data/rights/subjects/{profile_id}/export`
- `PATCH /crm/customer-data/rights/subjects/{profile_id}`
- `POST /crm/customer-data/rights/subjects/{profile_id}/restriction`
- `DELETE /crm/customer-data/rights/subjects/{profile_id}/restriction`
- `GET /crm/customer-data/rights/restrictions`
- `GET /crm/customer-data/rights/summary`

## Critérios de validação

- migração `0101` em upgrade e downgrade;
- isolamento RLS das novas tabelas;
- pacote sem `value_hash`;
- validação de correção vazia ou nula;
- ingestão rejeitada com `processing_restricted`;
- backend, front-end, tipos e auditoria de segurança aprovados.
