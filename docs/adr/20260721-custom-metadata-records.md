# ADR - Registros personalizados seguros

Data: 21 de julho de 2026.

## Decisao

Registros personalizados sao persistidos em JSONB somente depois de validados contra
uma versao publicada e normalizada da entidade. Cada registro guarda a versao do schema,
controle de concorrencia e uma chave opcional de idempotencia.

## Garantias

- consultas sempre filtram `company_id`, definicao e identificador;
- campos desconhecidos e tipos invalidos sao rejeitados;
- campos obrigatorios, valores padrao e unicidade sao aplicados no backend;
- leitura mascara campos sem permissao e escrita bloqueia campos proibidos;
- atualizacoes exigem a versao conhecida pelo cliente;
- eventos carregam apenas identificadores, nunca valores do registro;
- revisoes guardam historico enquanto o registro existe;
- exclusao remove fisicamente registro e revisoes para nao reter conteudo apagado;
- auditoria residual guarda apenas quem, quando, acao e identificadores tecnicos.

## Consequencias

O primeiro runtime e portavel e evita DDL dinamico por empresa. Consultas analiticas
complexas e indices especializados serao adicionados conforme metadados de busca e
volume real, sem expor SQL arbitrario.
