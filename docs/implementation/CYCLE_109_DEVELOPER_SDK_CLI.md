# Ciclo 109 - SDK e CLI para desenvolvedores

- contrato canonico de pacotes movido para o SDK publico;
- chave Ed25519 privada gravada com permissao `0600` e nunca impressa;
- comandos `keygen`, `sign` e `verify`;
- digest SHA-256 calculado diretamente do artefato;
- contrato de saida compativel com a API do marketplace;
- backend e CLI utilizam a mesma serializacao e verificacao criptografica.
