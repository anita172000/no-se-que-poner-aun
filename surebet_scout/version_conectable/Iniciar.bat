@echo off
chcp 65001 >nul
title Surebet Scout
cd /d "%~dp0"

set "PY="
where python >nul 2>nul && set "PY=python"
if not defined PY (where py >nul 2>nul && set "PY=py")
if not defined PY (
  echo.
  echo  No encuentro Python en este ordenador.
  echo  Instalalo desde https://www.python.org/downloads/
  echo  IMPORTANTE: en la primera pantalla marca "Add python.exe to PATH".
  echo  Despues vuelve a hacer doble clic en Iniciar.bat
  echo.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Preparando Surebet Scout por primera vez, tarda un minuto...
  %PY% -m venv .venv || goto error
  ".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
  ".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt || goto error
)
if not exist ".env" copy ".env.example" ".env" >nul

echo.
echo  Surebet Scout se abre en tu navegador: http://127.0.0.1:8050
echo  Deja esta ventana abierta mientras lo uses. Para cerrarlo, cierra esta ventana.
echo.
".venv\Scripts\python.exe" app.py
pause
exit /b 0

:error
echo.
echo  Algo fallo al preparar el programa. Haz una captura de esta ventana y pasamela.
pause
exit /b 1
