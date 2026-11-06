@echo off
setlocal
set "ROOT=%~dp0"
set "PYTHON=%ROOT%backend\.venv\Scripts\python.exe"
set "VITE=%ROOT%node_modules\.bin\vite.cmd"

if not exist "%PYTHON%" (
  echo No encuentro el entorno de Python en backend\.venv.
  echo Instala primero las dependencias del backend.
  pause
  exit /b 1
)
if not exist "%VITE%" (
  echo No encuentro Vite en node_modules.
  echo Instala primero las dependencias del frontend con pnpm install.
  pause
  exit /b 1
)

start "Yuyari - API" cmd.exe /k "cd /d %ROOT%backend && .venv\Scripts\python.exe manage.py migrate && .venv\Scripts\python.exe manage.py bootstrap_admin && .venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000"
start "Yuyari - Web" cmd.exe /k "cd /d %ROOT% && node_modules\.bin\vite.cmd --host 0.0.0.0"
timeout /t 5 /nobreak >nul
start "" http://localhost:5173

endlocal
