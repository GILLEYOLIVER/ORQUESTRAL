# Ciclo 112 - Endurecimento RLS e testes hostis

- RLS forcado nas tabelas legadas de CDC e direitos de titulares;
- inventario automatico de toda tabela com `company_id`;
- falha automatica quando RLS nao estiver habilitado e forcado;
- teste real com o papel `orkestral_app` e troca hostil de tenant;
- contrato que impede segredos OIDC nas respostas;
- `marketing_public_page_registry` e a unica excecao: localizador publico por
  UUID, sem conteudo de formulario, usado apenas para resolver o tenant antes
  da consulta protegida.
