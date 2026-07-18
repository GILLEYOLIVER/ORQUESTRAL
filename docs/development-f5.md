# Desenvolvimento com F5

A raiz do projeto contém uma configuração compartilhada do VS Code para iniciar o ambiente local com Docker Compose.

## Uso

1. Abra a raiz do repositório no VS Code.
2. Inicie o Docker Desktop.
3. Pressione `F5`.
4. Escolha `Orkestral: F5 iniciar e abrir interface`, caso o VS Code solicite uma configuração.

O processo executa `scripts/dev.ps1` no Windows e `scripts/dev.sh` no macOS/Linux, aguarda `http://localhost/health` responder e abre `http://localhost/app` no Chrome.

No Windows, o VS Code executa `scripts/dev.ps1` com Windows PowerShell. No macOS e Linux, executa `scripts/dev.sh` com Bash.

As tarefas adicionais ficam disponíveis em **Terminal > Executar Tarefa** para iniciar sem rebuild, encerrar, consultar status e acompanhar logs.
