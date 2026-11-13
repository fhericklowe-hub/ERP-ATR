@echo off
rem Restaure l'ERP depuis une sauvegarde : la base et les pieces jointes de la date indiquee.
rem Sans date, affiche les sauvegardes disponibles.   Exemple : restaurer.bat 20261113-020000
setlocal
cd /d "%~dp0"

if "%~1"=="" (
  echo Sauvegardes disponibles ^(date, puis taille de la base^) :
  docker compose --profile outils run --rm -T sauvegarde lister
  echo.
  echo Pour restaurer : restaurer.bat AAAAMMJJ-HHMMSS
  exit /b 1
)

echo ATTENTION : toutes les donnees actuelles de l'ERP vont etre remplacees par celles de la sauvegarde %~1.
echo Les utilisateurs seront deconnectes pendant l'operation.
set /p REPONSE=Tapez OUI pour continuer : 
if /i not "%REPONSE%"=="OUI" (
  echo Annule : rien n'a ete modifie.
  exit /b 1
)

echo === Sauvegarde de securite de l'etat actuel ===
docker compose --profile outils run --rm -T sauvegarde sauvegarder || (echo ECHEC de la sauvegarde de securite : rien n'a ete modifie. & exit /b 1)

echo === Restauration ===
docker compose stop web backend worker
docker compose --profile outils run --rm -T sauvegarde restaurer %~1 --oui
set RESULTAT=%errorlevel%
docker compose start backend worker web

if not "%RESULTAT%"=="0" (
  echo.
  echo ECHEC de la restauration : la base est restee comme avant. L'ERP est relance.
  exit /b 1
)
echo.
echo Restauration terminee. L'ERP est relance.
