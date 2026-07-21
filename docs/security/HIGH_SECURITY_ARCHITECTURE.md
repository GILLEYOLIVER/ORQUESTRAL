# Arquitetura de alta segurança e eliminação de dados

## 1. Princípio

A Orkestral utiliza defesa em profundidade. Nenhum controle isolado é tratado como suficiente e nenhum documento deve prometer que o sistema é inviolável. O objetivo é prevenir, detectar, conter e recuperar com segurança.

As decisões seguem OWASP API Security, OWASP ASVS e NIST SSDF.

## 2. Ameaças consideradas

| Ameaça                        | Exemplo                                                     | Controle principal                                                                                                           |
| ----------------------------- | ----------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| Acesso horizontal             | Usuário da empresa A tenta abrir um objeto da empresa B     | Todas as consultas novas exigem `company_id`; vínculos críticos de projetos possuem chaves estrangeiras compostas por tenant |
| Autorização quebrada          | Usuário autenticado chama uma rota administrativa           | Permissões específicas por rota e módulo ativo                                                                               |
| Roubo de sessão               | Token obtido em navegador ou dispositivo comprometido       | Tokens curtos com `iss`, `aud`, `sid`, `jti` e expiração; revogação de sessões; HTTPS e HSTS                                 |
| CSRF e requisições cross-site | Site externo tenta alterar dados usando sessão do navegador | Validação de `Origin`, Fetch Metadata, CORS explícito e exigência de JSON                                                    |
| Abuso de recursos             | Upload ou chamadas excessivas                               | Limite de corpo, rate limiting por IP e identidade, paginação e limites de schema                                            |
| Injeção                       | Entrada manipulada em filtros ou comandos                   | SQLAlchemy parametrizado, schemas estritos e valores enumerados                                                              |
| Exposição por log             | Senha, token ou documento aparece em observabilidade        | Logs estruturados sem corpo, autorização, cookies ou conteúdo de documentos                                                  |
| Vazamento de banco            | Cópia indevida do banco                                     | TLS obrigatório remotamente, criptografia do volume no provedor e AES-256-GCM em campos de alto impacto                      |
| Vazamento de bucket           | Objeto lido fora da aplicação                               | HTTPS e SSE-C por objeto com chave derivada fora do bucket                                                                   |
| Manipulação de ciphertext     | Registro criptografado é alterado                           | AES-GCM autentica conteúdo e contexto; falha de autenticação bloqueia a leitura                                              |
| Sobrescrita concorrente       | Dois usuários alteram o mesmo projeto                       | Campo de versão e atualização condicional com resposta `409`                                                                 |
| Exclusão incompleta           | Empresa é apagada, mas arquivos e tokens permanecem         | Processo de purge com reautenticação, objetos, cache, auditoria, tenant, sessões e usuários órfãos                           |
| Cadeia de dependências        | Biblioteca vulnerável entra no build                        | Dependências fixadas por versão, CI e atualização controlada                                                                 |

## 3. Criptografia

### 3.1 Senhas

Senhas nunca são criptografadas de forma reversível. Elas são transformadas por Argon2id com salt individual. A senha original não deve ser registrada, exportada, enviada para logs ou recuperada por administradores.

### 3.2 Campos sensíveis

Campos de risco e outros registros classificados utilizam AES-256-GCM com nonce aleatório. A chave efetiva é derivada por domínio a partir de `ENCRYPTION_KEY`. O `company_id` participa como dado autenticado para impedir a transferência de ciphertext entre tenants.

`ENCRYPTION_PREVIOUS_KEYS` permite leitura durante rotação. A chave nova deve ser a primeira, os dados devem ser recriptografados e a chave anterior deve ser removida depois da janela de migração.

### 3.3 Arquivos

Quando `OBJECT_STORAGE_ENABLED=true` em ambiente remoto, `OBJECT_STORAGE_SSE_ENABLED=true` é obrigatório. Cada objeto é enviado com SSE-C e chave de 256 bits derivada para a finalidade de armazenamento.

Objetos antigos gravados sem SSE precisam ser baixados em ambiente controlado e reenviados com a proteção ativa antes de obrigar SSE em um ambiente existente.

### 3.4 Transporte

Ambientes remotos exigem:

- PostgreSQL com `sslmode=require` ou `ssl=require`;
- Redis com `rediss://`;
- armazenamento de objetos com `https://`;
- frontend e API publicados somente em HTTPS;
- HSTS habilitado.

### 3.5 Backups

Backups devem ser criptografados com chave diferente da aplicação e ter expiração automática máxima definida pelo contrato. Uma eliminação não reescreve instantaneamente cópias imutáveis. O tenant apagado deve entrar em uma lista de não restauração e desaparecer quando a janela expirar.

Para dados de teste, utilizar retenção máxima de 7 dias. Para futura produção, definir prazo jurídico e técnico antes de receber clientes reais.

## 4. Eliminação segura de uma empresa

Endpoint administrativo:

```text
POST /companies/{company_id}/purge
```

Proteções obrigatórias:

1. permissão `platform.companies.update`;
2. reautenticação com a senha da conta administrativa;
3. confirmação literal `PURGE:{slug}`;
4. aceite da política de expiração dos backups;
5. bloqueio se existirem objetos e o armazenamento estiver inacessível.

Sequência:

1. localizar todos os objetos externos do tenant;
2. apagar os objetos do bucket;
3. revogar sessões selecionadas na empresa;
4. apagar auditorias e tentativas de acesso relacionadas;
5. apagar a empresa, acionando `ON DELETE CASCADE` para dados do tenant;
6. apagar usuários sem qualquer outra empresa, incluindo hash de senha e tokens;
7. invalidar cache e chaves Redis do tenant;
8. impedir restauração do tenant a partir de backup;
9. aguardar expiração das cópias imutáveis conforme a política.

O endpoint não oferece restauração. Exportações necessárias devem ser feitas antes da confirmação.

## 5. Chaves e segredos

Nunca colocar no GitHub:

- `JWT_SECRET`;
- `ENCRYPTION_KEY`;
- chaves anteriores;
- senhas de banco e Redis;
- credenciais do bucket;
- chaves de IA e integrações.

Produção deverá utilizar gerenciador de segredos com trilha de acesso. A rotação emergencial deve revogar sessões, trocar JWT, banco, Redis, bucket e integrações, preservando temporariamente somente as chaves antigas necessárias para recriptografia.

## 6. Configuração de proxy

`X-Forwarded-For` só é aceito quando o endereço direto está em `SECURITY_TRUSTED_PROXY_IPS`. Sem isso, um atacante poderia forjar o IP e contornar limites de requisição.

Cadastrar apenas IPs documentados do proxy ou balanceador. Nunca utilizar `0.0.0.0/0` ou confiar em qualquer origem.

## 7. Resposta a incidente

1. bloquear ou suspender o tenant afetado;
2. revogar sessões e tokens;
3. preservar logs sem conteúdo sensível;
4. rotacionar os segredos potencialmente expostos;
5. identificar objetos e empresas acessados pelos `request_id`;
6. corrigir e implantar antes de reabrir;
7. comunicar responsáveis conforme requisitos legais;
8. registrar causa raiz e teste de regressão.

## 8. Controles que dependem da infraestrutura

O código não consegue sozinho garantir:

- criptografia física dos discos do PostgreSQL;
- criptografia e retenção dos backups do provedor;
- proteção do host Docker;
- MFA da conta do provedor e do GitHub;
- firewall e rede privada;
- varredura contínua de imagens e dependências;
- WAF, proteção DDoS e alertas externos.

Esses controles são obrigatórios antes da produção real e devem ser confirmados no painel de cada provedor.

## 9. Checklist antes de clientes reais

- TLS confirmado no banco, Redis, API e bucket;
- discos e backups criptografados;
- MFA obrigatório em GitHub e provedores;
- branch protection e revisão de PR;
- análise de dependências e imagens no CI;
- teste de autorização entre dois tenants;
- teste de purge com empresa fictícia;
- restauração testada sem reintroduzir tenant apagado;
- chaves rotacionadas e fora do repositório;
- alertas de login, erro, rate limit e acesso administrativo;
- pentest independente antes da liberação pública.
