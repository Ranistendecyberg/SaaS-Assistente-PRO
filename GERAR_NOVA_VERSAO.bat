@echo off
setlocal
title Gerar nova versao - SaaS Assistente PRO

set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python314\python.exe"
if not exist "%PYTHON_EXE%" (
  echo Python nao encontrado em: %PYTHON_EXE%
  echo Entre em contato com o suporte antes de continuar.
  pause
  exit /b 1
)

set /p "RELEASE_VERSION=Informe a nova versao (exemplo 1.9.1): "
if "%RELEASE_VERSION%"=="" exit /b 1

echo.
echo Gerando executavel, instalador e assinatura de seguranca...
echo Este processo pode demorar alguns minutos.
echo.

"%PYTHON_EXE%" build_release.py "%RELEASE_VERSION%"
if errorlevel 1 (
  echo.
  echo A geracao nao foi concluida. Nenhuma atualizacao foi publicada.
  pause
  exit /b 1
)

echo.
echo Versao gerada. Agora publique o instalador e use o Gerador Admin
echo para informar o link HTTPS e selecionar o mesmo EXE para calcular o SHA-256.
pause
endlocal
