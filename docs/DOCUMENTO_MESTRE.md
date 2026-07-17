# Documento Mestre de Desenvolvimento — Orkestral

**Versão:** 1.1

Este é o índice oficial da especificação principal do repositório.

A versão 1.1 incorpora o fluxo de desenvolvimento pelo VS Code com inicialização por `F5`, tarefas compartilhadas, script PowerShell, abertura automática da interface e acesso administrativo estritamente local.

## Partes

1. [Fundação, arquitetura e experiência F5](master/01-fundacao.md)
2. [Fases 2 a 5 — identidade, permissões, módulos e plugins](master/02-fases-2-a-5.md)
3. [Fases 6 a 10 — n8n, agentes, conhecimento, automações e dashboards](master/03-fases-6-a-10.md)
4. [Fases 11 a 15, ordem de execução e regras finais](master/04-fases-11-a-15-e-regras.md)

## Próxima fase do projeto

Com as fases 1 a 5 implementadas, a próxima fase prevista é:

**Fase 6 — Integração com n8n**

O trabalho deverá começar pelo cliente interno centralizado em `modules/workflows/services/n8n_client.py`, seguido das tabelas de workflows e execuções, segurança multiempresa e interface da Orkestral.

## Regra de atualização

Toda mudança relevante de arquitetura, infraestrutura ou ordem de execução deverá atualizar este documento no mesmo pull request ou em um pull request documental associado.
