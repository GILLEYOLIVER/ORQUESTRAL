# Instalação do Orkestral no macOS e Windows

Os instaladores preparam o ambiente de desenvolvimento local completo. O
Orkestral continua sendo uma plataforma web em containers, não um aplicativo
desktop isolado.

## O que o instalador faz

1. confirma o sistema operacional;
2. verifica o Docker Desktop e containers Linux;
3. oferece a instalação oficial do Docker quando ele não existe;
4. preserva qualquer `.env` existente;
5. na primeira instalação, gera segredos criptograficamente aleatórios;
6. protege o `.env` e o arquivo de credenciais;
7. inicia PostgreSQL, Redis, API, worker, web, n8n, armazenamento e Nginx;
8. recupera o n8n quando seu pool perde a conexão com o PostgreSQL;
9. cria um atalho para `http://localhost/app`.

Nenhuma senha é incluída no GitHub ou escrita no bundle do navegador.

## macOS

No Finder, abra `installers/macos/Install-Orkestral.command`, ou no Terminal:

```bash
./installers/macos/Install-Orkestral.command
```

O instalador usa Docker Desktop. Se o comando `docker` não existir e o Homebrew
estiver disponível, ele instala o aplicativo oficial pelo cask. O macOS poderá
solicitar sua senha para concluir a instalação do Docker.

As credenciais da primeira instalação ficam em:

```text
~/Library/Application Support/Orkestral/local-credentials.txt
```

Somente o usuário atual recebe permissão de leitura.

## Windows

Clique duas vezes em:

```text
installers\windows\Install-Orkestral.cmd
```

Ou execute no PowerShell:

```powershell
.\installers\windows\Install-Orkestral.ps1
```

Quando necessário, o instalador usa o `winget` para instalar o Docker Desktop.
Se o Windows solicitar reinicialização, reinicie e execute o instalador novamente.

As credenciais ficam em:

```text
%LOCALAPPDATA%\Orkestral\local-credentials.txt
```

O diretório recebe uma ACL exclusiva para o usuário atual.

## Verificar sem instalar

macOS:

```bash
./installers/macos/Install-Orkestral.command --check-only
```

Windows:

```powershell
.\installers\windows\Install-Orkestral.ps1 -CheckOnly
```

## Instalar sem iniciar

Use `--no-start` no macOS ou `-NoStart` no Windows.

## Atualizar

Depois de atualizar o repositório, execute:

```bash
./scripts/dev.sh start
```

No Windows:

```powershell
.\scripts\dev.ps1 start
```

Os scripts reutilizam o `.env` e os volumes existentes. Eles não apagam dados.

## Encerrar

macOS:

```bash
./scripts/dev.sh stop
```

Windows:

```powershell
.\scripts\dev.ps1 stop
```

Não utilize `down -v` a menos que queira remover deliberadamente todos os dados.
