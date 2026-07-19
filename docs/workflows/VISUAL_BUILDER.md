# Construtor visual de automacoes

A Orkestral persiste uma definicao neutra com `nodes`, `connections`, `variables` e `version`. O compilador converte essa definicao para n8n apenas ao sincronizar ou publicar; credenciais permanecem no cofre.

Cada salvamento cria uma entrada imutavel em `workflow_versions`. Publicacao exige validacao sem erros, sincroniza o compilado no n8n e ativa a versao. Historico, comparacao, restauracao, duplicacao e execucoes ficam disponiveis pela API e pelo canvas.

O catálogo pode apresentar blocos planejados, mas a publicação aceita somente os blocos marcados como suportados em `GET /api/workflows/blocks/compatibility`. Um bloco sem adaptador interrompe a compilação com erro explícito; ele nunca é convertido silenciosamente em `noOp`.
