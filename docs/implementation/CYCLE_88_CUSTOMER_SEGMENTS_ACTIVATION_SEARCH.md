# Ciclo 88 — segmentos, ativação e busca de clientes

## Entrega

- segmentos com definição tipada e versão;
- materialização reproduzível de membros;
- exclusão obrigatória de perfis sob restrição;
- filtro opcional por finalidade e canal de consentimento;
- publicação controlada;
- ativação transacional em audiência de campanha;
- busca textual por nome e busca exata por identidade hash;
- respostas com dica mascarada, sem identidade bruta;
- painel administrativo responsivo;
- RLS forçada em segmentos, membros e ativações.

## Segurança da ativação

Uma ativação somente inclui o contato quando:

1. o segmento está publicado;
2. o perfil ainda pertence à mesma empresa;
3. não existe restrição ativa de processamento;
4. existe contato principal;
5. há consentimento de marketing concedido e não expirado;
6. o canal do consentimento é compatível com a campanha;
7. a campanha está disponível e pertence à mesma empresa.

Nenhum webhook ou arquivo externo é produzido automaticamente.

## Contratos

- `GET /crm/customer-data/segments`
- `POST /crm/customer-data/segments`
- `POST /crm/customer-data/segments/{id}/materialize`
- `POST /crm/customer-data/segments/{id}/publish`
- `POST /crm/customer-data/segments/{id}/activate`
- `GET /crm/customer-data/segments/search/profiles?q=...`

## Validação

- migração `0102` em upgrade e downgrade;
- RLS e permissões;
- materialização sem perfil restrito;
- ativação somente com consentimento;
- busca sem identidade bruta;
- testes backend/frontend, tipos, build e auditoria de segurança.
