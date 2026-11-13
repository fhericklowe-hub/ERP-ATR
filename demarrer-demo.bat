@echo off
rem Lance l'ERP sur ce poste pour une demonstration, avec des donnees fictives.
rem Il faut Python 3.12 ou plus (https://www.python.org, cocher "Add python.exe to PATH") et Node.js LTS (https://nodejs.org).
setlocal
cd /d "%~dp0"

where python >nul 2>nul || (echo Python n'est pas installe. Voir https://www.python.org/downloads/ & pause & exit /b 1)
where npm >nul 2>nul || (echo Node.js n'est pas installe. Voir https://nodejs.org & pause & exit /b 1)

echo === Preparation du serveur (quelques minutes la premiere fois) ===
cd backend
if not exist .venv\Scripts\python.exe python -m venv .venv || goto erreur
.venv\Scripts\python.exe -m pip install --quiet --disable-pip-version-check -r requirements.txt || goto erreur
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
