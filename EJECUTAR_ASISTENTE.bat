@echo off
REM ============================================================
REM  Medellin Bienestar AI - Asistente (Windows)
REM  Doble clic para iniciar. No requiere conocimientos tecnicos.
REM ============================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo ===========================================================
echo   MEDELLIN BIENESTAR AI - Asistente de salud territorial
echo ===========================================================
echo.

REM --- 1. Verificar que Python este instalado ---
where python >nul 2>&1
if errorlevel 1 (
    echo [!] No se encontro Python en este equipo.
    echo.
    echo     Para usar el asistente, instala Python 3.11 desde:
    echo         https://www.python.org/downloads/
    echo     IMPORTANTE: marca la casilla "Add Python to PATH"
    echo     durante la instalacion. Luego vuelve a dar doble clic aqui.
    echo.
    pause
    exit /b 1
)

echo [1/3] Python detectado:
python --version

REM --- 2. Instalar dependencias del asistente solo si faltan ---
echo.
echo [2/3] Verificando dependencias (solo la primera vez tarda)...
python -c "import streamlit" >nul 2>&1
if errorlevel 1 (
    echo     Instalando interfaz web... por favor espera.
    python -m pip install --quiet --disable-pip-version-check -r asistente\requirements.txt
)

REM --- 3. Lanzar el asistente ---
echo.
echo [3/3] Abriendo el asistente en tu navegador...
echo     Si no abre solo, entra a: http://localhost:8501
echo     Para cerrar: cierra esta ventana negra.
echo.
python -m streamlit run asistente\app.py

pause
