# Orkestral Plugin SDK

Contrato público e independente do núcleo para integrações da plataforma Orkestral.

## Capacidades

- Manifesto tipado com autenticação, configuração, ferramentas, gatilhos e ações.
- Validação central de campos obrigatórios sem registrar segredos.
- Teste de conexão assíncrono com timeout e isolamento de falhas.
- Pontos de extensão para execução, renovação de tokens e webhooks.
- Descoberta automática de plugins Python pelo entry point `orkestral.plugins`.
- CLI para gerar chaves, assinar e verificar pacotes do marketplace.

## Plugin externo

Implemente `BasePlugin`, publique uma instância ou classe e declare o entry point:

```toml
[project.entry-points."orkestral.plugins"]
meu_plugin = "meu_pacote:MeuPlugin"
```

Depois que o pacote estiver instalado, o runtime o descobre sem alteração no núcleo. O catálogo do tenant continua sendo controlado pelo banco da plataforma.

## Pacote assinado

```bash
orkestral-plugin keygen \
  --private-key .secrets/publicador.key \
  --public-key publicador.pub

orkestral-plugin sign \
  --plugin-code meu_plugin \
  --publisher-code minha_empresa \
  --version 1.0.0 \
  --manifest manifest.json \
  --artifact dist/meu_plugin.whl \
  --private-key .secrets/publicador.key \
  --min-platform-version 0.13.0 \
  --permission plugins.view \
  --output release.json

orkestral-plugin verify \
  --contract release.json \
  --public-key publicador.pub
```

A chave privada recebe permissão `0600`, nunca é impressa e não deve ser enviada
ao GitHub. O arquivo `release.json` é compatível com a rota de publicação do
marketplace.
