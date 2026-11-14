@echo off
rem Mise a jour du serveur ERP : sauvegarde, nouvelle version, migrations.
rem A lancer sur le serveur, dans le dossier du projet, APRES avoir remplace les fichiers par la nouvelle version
rem (ou si le dossier vient de git, ce script recupere lui-meme la derniere version).
setlocal
cd /d "%~dp0"

where docker >nul 2>&1 || (echo Docker n'est pas installe ou pas demarre sur ce poste. Cette mise a jour se lance sur le serveur. & exit /b 1)
if not exist .env (echo Fichier .env introuvable : ce dossier n'est pas celui du serveur. & exit /b 1)

echo.
echo === 1/4  Sauvegarde avant la mise a jour ===
call sauvegarder.bat
if errorlevel 1 (
  echo.
  echo Mise a jour ANNULEE : la sauvegarde a echoue, rien n'a ete modifie.
  exit /b 1
)

if exist .git (
  echo.
  echo === 2/4  Recuperation de la derniere version ===
  git pull --ff-only
  if errorlevel 1 (
    echo Mise a jour ANNULEE : git n'a pas pu recuperer la derniere version.
    exit /b 1
  )
) else (
  echo.
  echo === 2/4  Fichiers : version deja en place dans ce dossier ===
)

echo.
echo === 3/4  Reconstruction et redemarrage ===
docker compose up -d --build
if errorlevel 1 (
  echo.
  echo ECHEC du redemarrage. La sauvegarde faite a l'etape 1 est dans le dossier "sauvegardes".
  exit /b 1
)

echo.
echo === 4/4  Migrations de la base ===
rem Le serveur les applique deja au demarrage ; on attend qu'il reponde puis on verifie qu'il n'en reste aucune.
set ESSAIS=0
:attente
docker compose exec -T backend python manage.py migrate --noinput >migration.tmp 2>&1
if not errorlevel 1 goto migre
set /a ESSAIS+=1
if %ESSAIS% GEQ 20 goto echec
timeout /t 5 /nobreak >nul
goto attente

:migre
type migration.tmp
del migration.tmp >nul 2>&1
echo.
echo Mise a jour terminee. Si un nouveau role est apparu, attribuez-le dans Administration ^> Comptes.
exit /b 0

:echec
type migration.tmp
del migration.tmp >nul 2>&1
echo.
echo ECHEC des migrations. Gardez cet ecran et la sauvegarde du dossier "sauvegardes", puis prevenez la personne qui maintient l'ERP.
exit /b 1
