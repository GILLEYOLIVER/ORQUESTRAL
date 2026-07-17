# DOCUMENTO MESTRE — FASES 11 A 15 E REGRAS FINAIS

# 16. FASE 11 — AUDITORIA E SEGURANÇA

## Objetivo

Registrar ações importantes e proteger o sistema.

Crie `audit_events` com empresa, usuário, tipo de ator, ação, recurso, dados anteriores e posteriores, IP, user agent, request ID e data. Nunca registre senhas, tokens ou credenciais completas.

Implemente rate limiting, bloqueio por tentativas, validação de entrada, proteção contra injeção, CORS, cabeçalhos de segurança, expiração de sessão, revogação de tokens, criptografia e rotação de segredos, backup, recuperação de desastre, verificação de uploads, limites por plano e logs sem dados sensíveis.

Use exclusão lógica para registros importantes e rotinas administrativas para exclusão definitiva conforme políticas e legislação aplicável.

---

# 17. FASE 12 — PLANOS, ASSINATURAS E LIMITES

## Objetivo

Permitir comercialização como SaaS.

Crie:

```text
plans
subscriptions
usage_records
```

Planos devem possuir preço, ciclo, limites e status. Assinaturas pertencem à empresa e guardam período, teste, cancelamento e status. Registros de uso devem guardar métrica, quantidade, data e metadados.

Limites possíveis: usuários, agentes, automações, execuções mensais, tokens, armazenamento, integrações, documentos e chamadas de API.

A aplicação deve verificar limites antes da execução e produzir mensagens claras.

---

# 18. FASE 13 — NOTIFICAÇÕES E APROVAÇÕES

## Objetivo

Criar uma central de eventos que exigem atenção humana.

Implemente notificações internas, por e-mail e por WhatsApp autorizado, central de aprovações, lembretes, estados de leitura e preferências por usuário.

Tabelas:

```text
notifications
notification_preferences
approval_requests
approval_actions
```

Uma automação deve poder pausar até a aprovação humana.

---

# 19. FASE 14 — TESTES

## Testes obrigatórios

### Unitários

Serviços, regras de negócio, permissões, validações, compilador de workflows, limites e consumo.

### Integração

PostgreSQL, Redis, armazenamento, n8n, provedores de IA e plugins.

### Segurança

Acesso entre empresas, escalonamento de privilégio, rotas sem autorização, manipulação de IDs, upload malicioso e vazamento de credenciais.

### Ponta a ponta

1. Criar empresa.
2. Criar usuário.
3. Ativar módulo.
4. Configurar plugin.
5. Criar agente.
6. Adicionar ferramenta.
7. Criar automação.
8. Executar.
9. Verificar logs.
10. Verificar consumo.

Não considere uma fase concluída sem testes automatizados.

---

# 20. FASE 15 — CI/CD E DEPLOY

## Pipeline

Configure GitHub Actions para instalar dependências, validar formatação, executar análise estática e testes, verificar migrações, construir imagens Docker, verificar vulnerabilidades, publicar imagens e implantar em ambiente autorizado.

Mantenha ambientes separados:

```text
development
testing
staging
production
```

Cada ambiente deve possuir banco, credenciais, configurações, domínio e logs separados.

O deploy deve incluir Nginx, HTTPS, renovação de certificados, backups, monitoramento, health checks, reinicialização, migração controlada e rollback.

---

# 21. ORDEM EXATA DE EXECUÇÃO

1. Criar monorepositório.
2. Configurar Docker e ambientes.
3. Configurar a experiência local com VS Code, tarefas e inicialização por `F5`.
4. Criar API e health checks.
5. Criar front-end e layouts.
6. Configurar PostgreSQL, Redis e migrações.
7. Criar empresas.
8. Criar usuários.
9. Criar autenticação.
10. Criar contexto multiempresa.
11. Criar papéis e permissões.
12. Criar catálogo de módulos.
13. Criar ativação de módulos por empresa.
14. Implementar CRM básico.
15. Criar SDK de plugins.
16. Implementar cofre de credenciais.
17. Criar plugins iniciais.
18. Criar cliente interno do n8n.
19. Criar workflows e histórico de execuções.
20. Criar agentes.
21. Criar abstração de provedores de IA.
22. Criar ferramentas dos agentes.
23. Criar confirmação de ações sensíveis.
24. Criar controle de tokens e custos.
25. Criar base de conhecimento.
26. Criar processamento assíncrono de documentos.
27. Criar construtor visual.
28. Criar compilador Orkestral para n8n.
29. Criar dashboards.
30. Criar auditoria.
31. Criar planos e assinaturas.
32. Criar central de notificações e aprovações.
33. Criar testes completos.
34. Criar pipeline CI/CD.
35. Preparar staging.
36. Executar auditoria de segurança.
37. Preparar produção.

---

# 22. REGRA DE ENTREGA DE CADA FASE

Ao concluir uma fase, apresente:

1. Resumo do implementado.
2. Arquivos criados.
3. Arquivos alterados.
4. Migrações.
5. Rotas.
6. Variáveis de ambiente.
7. Testes.
8. Comandos de execução.
9. Limitações.
10. Próxima fase recomendada.

Não avance escondendo erros conhecidos. Não utilize dados fictícios silenciosamente em produção. Não substitua integrações reais por simulações sem identificá-las claramente.

---

# 23. PADRÕES OBRIGATÓRIOS DE CÓDIGO

* Utilize tipagem.
* Separe regras de negócio das rotas.
* Use repositórios para banco e serviços para casos de uso.
* Evite importações circulares.
* Não coloque credenciais no código.
* Não misture dados entre empresas.
* Não permita que o front-end controle permissões reais.
* Não acople agentes diretamente a provedores.
* Não acople o sistema ao formato interno do n8n.
* Documente decisões importantes.
* Crie migrações reversíveis quando possível.
* Mantenha compatibilidade de APIs.
* Utilize UUID.
* Registre erros com request ID.
* Nunca registre segredos completos.
* Adicione testes a cada funcionalidade.

---

# 24. RESULTADO FINAL ESPERADO

Ao final, uma nova empresa deverá conseguir criar conta, cadastrar usuários, configurar permissões, escolher plano, ativar módulos, conectar serviços, cadastrar agentes, autorizar ferramentas, importar documentos, criar automações visuais, executar tarefas por linguagem natural, aprovar ações sensíveis, acompanhar execuções, consumo e custos, consultar dashboards e expandir a plataforma com módulos e plugins.

A complexidade técnica deve permanecer escondida do cliente final. A interface deve usar termos empresariais simples. A arquitetura deve continuar modular, segura e reutilizável.

Este documento deve ser tratado como a especificação principal do repositório Orkestral.
