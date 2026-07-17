# Desenvolvimento com F5

A raiz do projeto contém uma configuração compartilhada do VS Code para iniciar o ambiente local com Docker Compose.

## Uso

1. Abra a raiz do repositório no VS Code.
2. Inicie o Docker Desktop.
3. Pressione `F5`.
4. Escolha `Orkestral: F5 iniciar e abrir interface`, caso o VS Code solicite uma configuração.

O processo executa `scripts/dev.ps1`, aguarda `http://localhost/health` responder e abre `http://localhost/app` no Chrome.

As tarefas adicionais ficam disponíveis em **Terminal > Executar Tarefa** para iniciar sem rebuild, encerrar, consultar status e acompanhar logs.
