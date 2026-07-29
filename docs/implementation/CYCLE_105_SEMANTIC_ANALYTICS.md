# Ciclo 105 - Analytics semantico

## Entregas

1. Catalogo versionado de metricas com unidade, agregacao, origem e filtros.
2. Definicoes de relatorios publicaveis e execucao por compilador allowlist.
3. Dashboards configuraveis que referenciam somente relatorios da mesma empresa.

## Seguranca

- Nenhum SQL fornecido pelo usuario e executado.
- Tabelas, dimensoes, medidas, filtros e operadores sao contratos fechados.
- Valores usam bind parameters.
- Toda consulta inclui `company_id`.
- Resultados sao limitados a 500 linhas.
- Execucoes registram somente contagem, duracao e erro; nao duplicam dados empresariais.
- As quatro tabelas possuem RLS habilitado e forcado.
