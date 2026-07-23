# Ciclo 66 — Agendas, gatilhos e credenciais de agentes

## Objetivo

Permitir que agentes publicados recebam trabalho por agenda ou evento sem dar ao modelo acesso direto ao banco, aos segredos ou a ferramentas não autorizadas.

## Entrega

- agendas versionadas com rascunho, publicação, pausa e substituição;
- gatilhos versionados por tipo e versão de evento;
- vínculo explícito entre ferramenta habilitada e credencial da mesma empresa;
- dispatcher periódico no worker com bloqueio seguro;
- idempotência por agenda/horário e gatilho/evento;
- auditoria e eventos de domínio para configuração e despacho;
- painel administrativo responsivo em português;
- visualização segura para perfis somente leitura.

## Segurança

- toda consulta usa `company_id` como limite obrigatório;
- uma credencial de outra empresa nunca pode ser vinculada;
- o dispatcher valida ferramenta, vínculo, estado e validade da credencial;
- segredos continuam cifrados no módulo de integrações;
- o despacho persiste somente IDs de vínculo e uma impressão HMAC do objetivo;
- payloads de eventos externos não são transformados em instruções para o agente;
- operações de configuração exigem `agents.configure` no backend;
- consultas operacionais exigem `agents.view`.

## Fluxo operacional

1. Publique uma versão do agente.
2. Habilite as ferramentas permitidas para ele.
3. Em Integrações, cadastre a credencial necessária.
4. Vincule cada ferramenta à credencial correspondente.
5. Crie uma agenda ou gatilho como rascunho.
6. Revise e publique.
7. O worker localiza trabalhos devidos e cria um despacho `ready` ou `blocked`.
8. A fila recente informa bloqueios sem revelar segredos.

## Limite deste ciclo

O ciclo prepara e governa a fila segura. A execução efetiva de despachos `ready`, com política, orçamento, aprovação, modo sombra e trace, permanece para o próximo recorte do runtime.
## Validacao final

- API completa: 197 testes aprovados.
- Seguranca do middleware: 6 testes aprovados.
- Worker: 6 testes aprovados.
- Integracao: 19 testes aprovados.
- Web: lint, tipos, 13 testes unitarios e build aprovados.
- E2E: 7 cenarios aprovados e 2 ignorados conforme configuracao.
- Migracao: downgrade para `20260722_0082` e upgrade para `20260722_0083` aprovados.
- Stack local: oito servicos saudaveis, com `/health` e `/ready` operacionais.

O login automatico de desenvolvimento recebeu um balde de rate limit proprio, ativo somente
em `APP_ENV=local`. Rotas de autenticacao remota continuam usando a politica estrita e
fail-closed original.
