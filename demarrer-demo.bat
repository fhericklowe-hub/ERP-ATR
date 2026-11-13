@echo off
rem Lance l'ERP sur ce poste pour une demonstration, avec des donnees fictives.
rem Il faut Python 3.13 (https://www.python.org/downloads/release/python-3139/) et Node.js LTS (https://nodejs.org).
rem Une version plus recente de Python (3.15...) ne convient pas encore : certaines bibliotheques n'y sont pas disponibles.
setlocal
cd /d "%~dp0"

set PY=
for %%V in (3.13 3.12 3.14) do if not defined PY (py -%%V -c "" >nul 2>nul && set PY=py -%%V)
if not defined PY (
  echo Il faut Python 3.13. Une version plus recente ne convient pas encore.
  echo Installez-le depuis https://www.python.org/downloads/release/python-3139/
  echo ^(fichier "Windows installer 64-bit"^), puis relancez ce script.
  pause
  exit /b 1
)
where npm >nul 2>nul || (echo Node.js n'est pas installe. Voir https://nodejs.org & pause & exit /b 1)

echo === Preparation du serveur (quelques minutes la premiere fois) ===
cd backend
rem Un environnement cree avec une autre version de Python est refait.
if exist .venv\Scripts\python.exe (.venv\Scripts\python.exe -c "import sys; sys.exit(sys.version_info[:2] not in ((3,12),(3,13),(3,14)))" || rmdir /s /q .venv)
if not exist .venv\Scripts\python.exe (%PY% -m venv .venv || goto erreur)
.venv\Scripts\python.exe -m pip install --quiet --disable-pip-version-check --only-binary=:all: -r requirements.txt || goto erreur
set DEBUG=True
.venv\Scripts\python.exe manage.py migrate --verbosity 0 || goto erreur
.venv\Scripts\python.exe manage.py donnees_demo || goto erreur
start "ERP - serveur" cmd /k ".venv\Scripts\python.exe manage.py runserver 8000"

echo === Preparation de l'application ===
cd ..\frontend
if not exist node_modules call npm install || goto erreur
start "ERP - application" cmd /k "npm run dev"

timeout /t 8 /nobreak >nul
start "" http://localhost:5173
echo.
echo L'ERP est ouvert dans le navigateur : http://localhost:5173
echo Pour l'arreter, fermez les deux fenetres "ERP - serveur" et "ERP - application".
pause
exit /b 0

:erreur
echo.
echo Une etape a echoue. Copiez le message ci-dessus pour obtenir de l'aide.
pause
exit /b 1
