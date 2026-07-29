# Identidade empresarial

## Provedores

Cada empresa pode registrar configuracoes OIDC ou SAML. Segredos de cliente sao
criptografados no backend e nunca retornam pela API. Um provedor novo permanece
em `configured`; ele so podera ficar `active` depois de um handshake real,
validacao de issuer, audience, nonce, assinatura e metadados.

Essa regra evita exibir um login SSO que ainda nao autentica de verdade.

## SCIM 2.0

O Orkestral oferece:

- `GET /scim/v2/Users`;
- `POST /scim/v2/Users`;
- `PATCH /scim/v2/Users/{id}` para ativar ou desativar o vinculo.

Tokens SCIM:

- sao exibidos somente na criacao;
- possuem 48 bytes de entropia;
- sao armazenados somente como hash;
- possuem empresa, escopos, papel padrao e expiracao;
- podem ser revogados;
- aplicam o contexto RLS antes de consultar dados.

Desativar um usuario por SCIM altera somente o vinculo com a empresa do token.
O cadastro global e os vinculos com outras empresas nao sao desativados.

## Limites atuais

- fluxo completo de callback OIDC ainda depende de homologacao com um provedor;
- validacao e consumo de assertion SAML ainda nao estao ativos;
- grupos SCIM e sincronizacao incremental serao extensoes do contrato atual.
