# Ciclo 107 - Portais externos governados

- Portais por empresa para clientes, parceiros, fornecedores e colaboradores.
- Modulos e identidade visual configurados por allowlist.
- Usuario externo continua usando a autenticacao central e permissoes normais.
- Convites de uso unico: somente SHA-256 e persistido; o token aparece uma vez.
- Aceite exige usuario autenticado e destinatario correto.
- Administracao exige `companies.update`.
- Definicoes, membros e convites possuem RLS forcado.
- Links administrativos somente leitura existentes continuam separados dos portais.
