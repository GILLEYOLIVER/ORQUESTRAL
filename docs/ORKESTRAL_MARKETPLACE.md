# Marketplace empresarial do Orkestral

## Objetivo

O marketplace distribui conectores, modulos, automacoes, metadados e agentes por
contratos versionados. Ele nao permite que um pacote de terceiro execute codigo
arbitrario dentro da API.

## Cadeia de confianca

1. Um administrador da plataforma registra um publicador e sua chave publica
   Ed25519.
2. O publicador calcula o SHA-256 do artefato e assina o contrato canonico.
3. O contrato inclui plugin, versao, manifesto, digest, compatibilidade e
   permissoes solicitadas.
4. A publicacao valida a assinatura e rejeita permissoes desconhecidas.
5. A instalacao repete a validacao, verifica dependencias e compatibilidade.
6. A empresa recebe uma instalacao auditada e isolada por RLS.

Chaves privadas nunca entram no Orkestral. A chave publica e seu fingerprint nao
sao segredos.

## Ciclo de vida

- `trusted`: publicador autorizado a assinar novas versoes;
- `revoked`: publicador bloqueado para novas instalacoes;
- `published`: versao disponivel e assinada;
- `revoked`: versao impedida de ser instalada;
- `installed`: versao ativa na empresa;
- `replaced`: versao preservada no historico apos atualizacao ou rollback.

O rollback cria uma nova entrada de historico, valida novamente o pacote
anterior e nao apaga evidencias.

## Modelo de seguranca

- instalacao exige `plugins.manage`;
- consulta exige `plugins.view`;
- cadastro de publicador e publicacao exigem administrador da plataforma;
- toda instalacao usa `company_id`;
- `company_plugin_installations` possui RLS habilitado e forcado;
- auditoria registra digest e fingerprint, nunca chave privada ou credencial;
- dependencias devem estar ativas na mesma empresa;
- somente permissoes existentes no catalogo podem ser solicitadas;
- runtimes continuam sendo adaptadores revisados do nucleo.

## Ferramentas para desenvolvedores

O SDK `0.2.0` fornece o contrato canonico consumido pela API e pela CLI
`orkestral-plugin`. Os comandos `keygen`, `sign` e `verify` permitem montar e
validar o pacote antes da publicacao. A chave privada permanece local, com
permissao `0600`.

O proximo recorte governa sandboxes e aprovacoes de promocao entre
desenvolvimento, teste, homologacao e producao.
