# Orkestral Plugin SDK

Contrato público e independente do núcleo para integrações da plataforma Orkestral.

## Capacidades

- Manifesto tipado com autenticação, configuração, ferramentas, gatilhos e ações.
- Validação central de campos obrigatórios sem registrar segredos.
- Teste de conexão assíncrono com timeout e isolamento de falhas.
- Pontos de extensão para execução, renovação de tokens e webhooks.
- Descoberta automática de plugins Python pelo entry point `orkestral.plugins`.

## Plugin externo

Implemente `BasePlugin`, publique uma instância ou classe e declare o entry point:

```toml
[project.entry-points."orkestral.plugins"]
meu_plugin = "meu_pacote:MeuPlugin"
```

Depois que o pacote estiver instalado, o runtime o descobre sem alteração no núcleo. O catálogo do tenant continua sendo controlado pelo banco da plataforma.
