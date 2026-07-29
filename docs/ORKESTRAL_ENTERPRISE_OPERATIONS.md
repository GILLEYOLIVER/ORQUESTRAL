# Operacao empresarial e confiabilidade

## Sinais obrigatórios

- disponibilidade e latência de `/health` e `/ready`;
- versão e commit em `/system/version`;
- erros por rota e empresa;
- saturação de API, worker, banco, Redis e armazenamento;
- profundidade, idade, retry e DLQ das filas;
- falhas de automações, integrações e agentes;
- consumo por empresa;
- sucesso, duração e idade dos backups.

Logs e métricas não podem conter senhas, tokens, cookies, prompts com segredos,
documentos completos ou cabeçalhos de autorização.

## Teste de carga seguro

```bash
./scripts/load-smoke.sh https://ambiente.example.com \
  --requests 500 --concurrency 20 \
  --max-error-rate 0.01 --max-p95-ms 1500
```

O teste usa somente GET em health/readiness, limita concorrência a 100 e falha
quando a taxa de erro ou o p95 excede o orçamento. Estresse autenticado deve
usar ambiente isolado, dados sintéticos e janela autorizada.

## SLO inicial sugerido

- disponibilidade mensal da API: 99,5%;
- p95 de leitura: abaixo de 1,5 segundo;
- erro 5xx: abaixo de 1%;
- jobs críticos no SLA: acima de 99%;
- backup íntegro e drill trimestral: 100%.

São referências para calibrar com tráfego e capacidade, não promessa comercial.

## Incidente e capacidade

Declare severidade, interrompa mudanças, preserve evidências sem dados sensíveis,
contenha o risco, recupere, valide isolamento e registre causa e prevenção.
API e web são stateless; workers escalam por fila. Migração e bootstrap rodam
uma vez. PostgreSQL, Redis e armazenamento precisam de redundância compatível
com o SLO. Um plano gratuito não é alta disponibilidade.

O contrato portátil dedicado está em
`infrastructure/deploy/dedicated/README.md`.
