# Dashboards e relatorios

O worker agrega a cada cinco minutos os eventos operacionais em `metric_daily_summaries`. A leitura do dashboard usa somente os resumos da empresa atual e cache Redis de cinco minutos.

Filtros aceitos: periodo, modulo, agente e workflow. Os mesmos filtros alimentam exportacoes CSV, XLSX e PDF. Conteudos de mensagens, documentos, credenciais e segredos nao entram nas tabelas de metricas.
