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
  echo Preparando Surebet Scout por primera vez, tarda unos minutos...
  %PY% -m venv .venv || goto error
  ".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
  ".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt || goto error
)
if not exist ".env" copy ".env.example" ".env" >nul

rem --- Captura de casas (solo la primera vez): sirve para añadir mas casas ---
if not exist ".captura_hecha" (
  echo.
  echo  ============================================================
  echo   PRIMERA VEZ: se abrira un navegador que pasa SOLO por cada
  echo   casa de apuestas. NO toques nada y NO inicies sesion.
  echo   Tarda unos 5-10 minutos. Despues se abre el programa.
  echo  ============================================================
  echo.
  ".venv\Scripts\python.exe" -m pip install --quiet playwright && ".venv\Scripts\python.exe" -m playwright install chromium && ".venv\Scripts\python.exe" herramientas\capturar_casas.py
  for /f "usebackq delims=" %%d in (`powershell -NoProfile -Command "[Environment]::GetFolderPath('Desktop')"`) do set "DESK=%%d"
  for %%f in (captura_casas_*.zip) do copy /y "%%f" "%DESK%\" >nul && echo. > ".captura_hecha"
  if exist ".captura_hecha" (
    echo.
    echo  ************************************************************
    echo   LISTO: en tu ESCRITORIO hay un archivo "captura_casas_....zip"
    echo   Pasaselo a Claude en el chat.
    echo  ************************************************************
    echo.
  ) else (
    echo  La captura no se pudo completar; el programa se abre igualmente.
  )
)

echo.
echo  Surebet Scout se abre en tu navegador: http://127.0.0.1:8050
echo  Deja esta ventana abierta mientras lo uses. Para cerrarlo, cierra esta ventana.
echo.
".venv\Scripts\python.exe" app.py
pause
exit /b 0

:error
echo.
echo  Algo fallo al preparar el programa. Haz una foto de esta ventana y pasamela.
pause
exit /b 1
