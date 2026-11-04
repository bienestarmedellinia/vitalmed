@echo off
REM ============================================================
REM  Pulso Medellin - Asistente (Windows)
REM  Doble clic para iniciar. No requiere conocimientos tecnicos.
REM  Disenado para ejecutarse sin errores incluso sin contexto.
REM ============================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo ===========================================================
echo   MEDELLIN BIENESTAR AI - Asistente de salud territorial
echo ===========================================================
echo.

REM --- 0. Comprobar que estamos en la carpeta correcta ---
if not exist "asistente\app.py" (
    echo [ERROR] Este archivo no esta en la carpeta del proyecto.
    echo         Debe estar junto a la carpeta "asistente".
    echo         Descomprime el ZIP completo y ejecuta el .bat desde dentro.
    echo.
    pause
    exit /b 1
)

REM --- 1. Detectar Python: probar 'py' y luego 'python' ---
set "PY="
py -3 --version >nul 2>&1 && set "PY=py -3"
if not defined PY (
    python --version >nul 2>&1 && set "PY=python"
)
if not defined PY (
    echo [!] No se encontro Python en este equipo.
    echo.
    echo     Instala Python 3.11 desde:  https://www.python.org/downloads/
    echo     IMPORTANTE: marca "Add Python to PATH" durante la instalacion.
    echo     Luego cierra esta ventana y vuelve a dar doble clic aqui.
    echo.
    pause
    exit /b 1
)
echo [1/4] Python detectado:
%PY% --version

REM --- 2. Verificar que exista el knowledge base ---
if not exist "outputs\kb\knowledge_base.json" (
    echo.
    echo [!] Falta outputs\kb\knowledge_base.json
    echo     Descargaste el proyecto incompleto. Vuelve a descargar el ZIP
    echo     completo desde GitHub (boton verde Code - Download ZIP).
    echo.
    pause
    exit /b 1
)
echo [2/4] Datos del asistente encontrados.

REM --- 3. Instalar dependencias solo si faltan (idempotente) ---
echo.
echo [3/4] Verificando interfaz web (solo la primera vez tarda)...
%PY% -c "import streamlit" >nul 2>&1
if errorlevel 1 (
    echo     Instalando... por favor espera 1-2 minutos.
    %PY% -m pip install --quiet --disable-pip-version-check -r asistente\requirements.txt
    if errorlevel 1 (
        echo.
        echo [ERROR] No se pudieron instalar las dependencias.
        echo         Revisa tu conexion a internet y vuelve a intentar.
        echo         Alternativa sin instalar nada: usa el asistente web
        echo         (ver COMO_EJECUTAR.md, Opcion B).
        echo.
        pause
        exit /b 1
    )
)

REM --- 4. Lanzar el asistente ---
echo [4/4] Abriendo el asistente en tu navegador...
echo.
echo     ^> Si no abre solo, entra a:  http://localhost:8501
echo     ^> Para CERRAR el asistente:  cierra esta ventana negra.
echo.
%PY% -m streamlit run asistente\app.py

pause
