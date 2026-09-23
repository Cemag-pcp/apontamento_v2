@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "SCRIPT=%SCRIPT_DIR%extrair_explosao.py"

where python >nul 2>nul
if errorlevel 1 (
    echo.
    echo ERRO: Python nao foi encontrado neste computador.
    echo Instale o Python em https://www.python.org/downloads/ ^(marque a
    echo opcao "Add python.exe to PATH" na instalacao^) e rode este arquivo de novo.
    echo.
    pause
    exit /b 1
)

python -c "import psycopg2" >nul 2>nul
if errorlevel 1 (
    echo Instalando dependencia necessaria ^(psycopg2-binary^)...
    python -m pip install --quiet psycopg2-binary
    if errorlevel 1 (
        echo.
        echo ERRO: Nao foi possivel instalar o psycopg2-binary automaticamente.
        echo Rode manualmente: python -m pip install psycopg2-binary
        echo.
        pause
        exit /b 1
    )
)

python "%SCRIPT%"

endlocal
