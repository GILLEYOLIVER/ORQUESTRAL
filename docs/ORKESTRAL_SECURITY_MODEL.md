# Modelo de seguranca do Orkestral

## Principios

1. Toda autorizacao relevante e aplicada no backend.
2. Toda consulta empresarial resolve e filtra `company_id`.
3. Permissoes sao cumulativas apenas dentro da mesma empresa e nunca atravessam tenants.
4. Negacao de campo remove o valor da resposta; negacao de escrita retorna `403`.
5. Segredos, conteudo protegido e credenciais nao entram em eventos, logs ou auditorias.
6. Proprietarios mantem uma rota de recuperacao administrativa auditavel.

## Camadas de autorizacao

- Sessao: usuario ativo, sessao valida e empresa selecionada.
- Catalogo global: permissao de modulo e operacao, como `metadata.records.update`.
- Politica: risco, escopo de plataforma e permissoes declaradas pelo campo.
- Metadados: regra de entidade, regra de campo, proprietario e compartilhamento explicito.
- Persistencia: filtros de tenant em todas as consultas e constraints relacionais.

Uma camada nunca substitui outra. O acesso somente e concedido quando todas as camadas aplicaveis permitem.

## Seguranca da plataforma de metadados

- Entidades configuradas sem regra correspondente negam acesso por padrao.
- Regra direta do usuario prevalece sobre regras dos papeis vinculados.
- Multiplos papeis concedem a uniao autorizada, respeitando o menor escopo configurado diretamente para o usuario.
- `owned` limita aos registros do usuario.
- `owned_shared` inclui registros recebidos por compartilhamento.
- `all` permite todos os registros da entidade, sempre dentro da empresa atual.
- Compartilhamento de edicao implica leitura; compartilhamento nunca concede exclusao.
- Regras inexistentes preservam compatibilidade com instalações anteriores.

## Auditoria e resposta a incidentes

Alteracoes de politica, compartilhamentos e revogacoes registram ator, empresa, entidade, destinatario e permissao, sem copiar valores do registro. Eventos usam identificadores e contagens para permitir investigacao e automacao segura.

## Segredos e configuracao por ambiente

- Arquivos `.env` reais sao ignorados e recusados pela verificacao de segredos do CI.
- Ambientes remotos recusam placeholders, segredos curtos, keyrings duplicados e reutilizacao entre JWT, criptografia e monitor.
- Producao exige cofre externo, TLS para PostgreSQL e Redis, HTTPS para armazenamento e rotacao coordenada.
- Rate limit, HSTS, validacao de origem e tipo de conteudo nao podem ser desligados remotamente.
- Segredos nunca devem ser gravados em imagem, codigo, logs ou documentacao; o provedor injeta os valores no processo.

## Protecao de acesso e abuso

- A API possui limite distribuido por Redis e identificadores protegidos por HMAC.
- Login e autorizacao administrativa usam limites independentes por conta e por IP para conter forca bruta e ataques distribuidos.
- Recuperacao de senha usa limite por conta e IP sem revelar se o e-mail existe.
- Rotas sensiveis falham fechadas quando o backend de protecao fica indisponivel.
- Somente proxies explicitamente confiaveis podem fornecer o IP original; o Nginx sobrescreve cabecalhos enviados pelo cliente.
- O gateway limita conexoes e rajadas, enquanto a aplicacao continua sendo a camada autoritativa.
- Respostas `429` informam tempo de espera sem revelar estado de conta ou detalhes internos.

## Evolucao planejada

- testes sistematicos de acesso cruzado em todos os dominios;
- conjuntos de permissoes e grupos compostos;
- explicacao administrativa da decisao de acesso;
- avaliacao controlada de PostgreSQL Row-Level Security;
- SSO, MFA, SCIM, dispositivos e politicas condicionais na fase empresarial de identidade.

## Verificacao RLS empresarial

- toda tabela interna com `company_id` deve ter RLS habilitado e forcado;
- a auditoria consulta `pg_catalog` e falha automaticamente em qualquer regressao;
- o teste hostil usa `orkestral_tenant_runtime`, troca o tenant da transacao e
  comprova que o registro externo deixa de existir;
- `marketing_public_page_registry` e a unica excecao documentada: armazena
  somente `public_id`, `company_id` e `page_id`, permitindo resolver o tenant
  de uma pagina publica antes das consultas protegidas;
- payloads de formularios, conteudo e demais dados nunca ficam nessa excecao.

O Ciclo 112 confirmou RLS habilitado e forcado em 237 tabelas internas.
