# Agentes de inteligência artificial

A Fase 7 implementa agentes multiempresa com instruções, modelo, limites, memória, ferramentas próprias e rastreabilidade de consumo. O agente nunca executa código ou altera dados diretamente: ele solicita uma ferramenta registrada e o Orkestral valida empresa, permissão, argumentos e estado antes de chamar um executor conhecido.

## Provedores

- `local`: determinístico, sem envio de dados a terceiros e disponível por padrão.
- `openai_compatible`: adaptador HTTP isolado para APIs compatíveis com `chat/completions`. A credencial existe somente no ambiente administrativo.

Ambos implementam `LanguageModelProvider.generate`, `stream` e `calculate_usage`. O domínio de agentes não depende diretamente de fornecedor.

## Ferramentas e confirmação

O catálogo inicial oferece consulta da empresa, consulta de automação e desativação de automação. Uma chamada é bloqueada quando a ferramenta não pertence ao agente, está desativada, exige permissão ausente ou recebe argumentos fora do esquema.

```text
/ferramenta orkestral.company.summary {}
```

A desativação de automação fica em `awaiting_confirmation`. Somente uma decisão autenticada pode aprovar ou rejeitar; a permissão é verificada novamente e a decisão entra na auditoria.

## Consumo

Cada interação registra empresa, usuário, agente, conversa, provedor, modelo, tokens, custo em milionésimos de dólar, ferramenta, duração e resultado. Argumentos e resultados passam pelo resumo protegido do Orkestral.
