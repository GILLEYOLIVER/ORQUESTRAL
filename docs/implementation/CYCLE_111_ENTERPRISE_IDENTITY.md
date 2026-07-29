# Ciclo 111 - Identidade empresarial

- provedores OIDC e SAML por empresa com segredo criptografado;
- configuracao permanece `configured` ate validacao real do provedor;
- tokens SCIM de uso servidor a servidor, exibidos somente uma vez;
- hash, expiracao, revogacao, escopos e papel padrao;
- provisionamento e desativacao limitados ao vinculo da empresa;
- tenant aplicado ao PostgreSQL antes de consultar o token SCIM;
- RLS forcado, auditoria e eventos transacionais.
