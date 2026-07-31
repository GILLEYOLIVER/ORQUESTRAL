@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-Orkestral.ps1" %*
if errorlevel 1 (
  echo.
  echo A instalacao nao foi concluida. Consulte a mensagem acima.
  pause
  exit /b 1
)
echo.
echo Instalacao concluida.
pause
