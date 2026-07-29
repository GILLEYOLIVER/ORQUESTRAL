# Plataforma para desenvolvedores

## Componentes entregues

- OpenAPI e APIs REST do nucleo;
- SDK publico de plugins;
- CLI para assinar e verificar pacotes;
- marketplace com publicadores, versoes, instalacao e rollback;
- pacotes de metadados com exportacao, validacao, instalacao e promocao;
- sandboxes logicos por empresa;
- solicitacoes de promocao com checksum e aprovacao segregada.

## Sandboxes

Um sandbox e um descritor de ambiente isolado pela empresa e nao uma copia
silenciosa da base principal. As politicas aceitas sao:

- `empty`: inicia sem dados empresariais;
- `synthetic`: utiliza somente dados ficticios;
- `masked`: permite importacao futura apenas apos mascaramento verificavel.

Producao nunca pode ser criada como sandbox. Todo sandbox expira e pode ser
arquivado.

## Promocao

Rotas permitidas:

```text
local -> development | testing
development -> testing | staging
testing -> staging
staging -> production
```

Cada solicitacao vincula tipo, referencia e SHA-256 do artefato. O solicitante
nao pode aprovar a propria promocao. A aprovacao autoriza a execucao, mas nao
marca o artefato como implantado; somente o executor real podera registrar
`applied` ou `failed`.

## Seguranca

- permissoes separadas para leitura, administracao e decisao;
- filtros por `company_id` em todas as consultas;
- RLS habilitado e forcado;
- auditoria e eventos transacionais;
- nenhum segredo ou conteudo do artefato em eventos;
- nenhum dado real copiado automaticamente;
- nenhuma execucao arbitraria de codigo de pacote.
