@echo off
chcp 65001 >nul
title Capturar casas de apuestas
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo.
  echo  Primero abre Iniciar.bat una vez para preparar el programa.
  echo  Despues vuelve a hacer doble clic aqui.
  echo.
  pause
  exit /b 1
)

echo.
echo  Preparando la herramienta (solo la primera vez tarda unos minutos)...
".venv\Scripts\python.exe" -m pip install --quiet playwright || goto error
".venv\Scripts\python.exe" -m playwright install chromium || goto error

echo.
echo  Ahora se abrira un navegador que ira pasando solo por cada casa de apuestas.
echo  NO toques nada y NO inicies sesion en ninguna. Tarda unos 5 minutos.
echo.
".venv\Scripts\python.exe" herramientas\capturar_casas.py || goto error

echo.
echo  Terminado. Se abre la carpeta: pasame el archivo .zip que empieza por "captura_casas".
start "" "%~dp0"
pause
exit /b 0

:error
echo.
echo  Algo fallo. Haz una captura de esta ventana y pasamela.
pause
exit /b 1
