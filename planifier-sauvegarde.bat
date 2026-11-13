@echo off
rem Programme la sauvegarde chaque nuit dans le Planificateur de taches de Windows.
rem Par defaut a 02:00 ; pour une autre heure : planifier-sauvegarde.bat 23:30
setlocal
cd /d "%~dp0"
set HEURE=02:00
if not "%~1"=="" set HEURE=%~1
schtasks /Create /SC DAILY /ST %HEURE% /TN "ERP ATR - Sauvegarde" /TR "\"%~dp0sauvegarder.bat\"" /F
if errorlevel 1 (
  echo Impossible de programmer la tache. Relancez ce script en tant qu'administrateur.
  exit /b 1
)
echo.
echo La sauvegarde est programmee chaque jour a %HEURE%.
echo Pour qu'elle tourne meme sans session ouverte : Planificateur de taches, "ERP ATR - Sauvegarde",
echo Proprietes, cocher "Executer meme si l'utilisateur n'est pas connecte".
echo Pour la supprimer : schtasks /Delete /TN "ERP ATR - Sauvegarde" /F
