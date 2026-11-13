@echo off
rem Sauvegarde du serveur ERP : la base de donnees et les pieces jointes, dans le dossier "sauvegardes".
rem A lancer sur le serveur, a la main ou chaque nuit (voir planifier-sauvegarde.bat).
setlocal
cd /d "%~dp0"
if not exist sauvegardes mkdir sauvegardes

docker compose --profile outils run --rm -T sauvegarde sauvegarder > sauvegardes\derniere.txt 2>&1
set RESULTAT=%errorlevel%
type sauvegardes\derniere.txt
(echo === %date% %time% === & type sauvegardes\derniere.txt & if not "%RESULTAT%"=="0" echo ECHEC) >> sauvegardes\journal.txt
if not "%RESULTAT%"=="0" (
  echo.
  echo ECHEC de la sauvegarde. Le detail est ci-dessus et dans sauvegardes\journal.txt
  exit /b 1
)

rem Copie facultative vers un autre disque ou un partage reseau : COPIE_VERS dans le fichier .env.
set COPIE=
if exist .env for /f "usebackq tokens=1,* delims==" %%a in (".env") do if /i "%%a"=="COPIE_VERS" set "COPIE=%%b"
if defined COPIE (
  robocopy "sauvegardes" "%COPIE%" erp-*.dump media-*.tar.gz /XO /R:2 /W:5 /NJH /NJS /NDL /NP >nul
  if errorlevel 8 (
    echo ECHEC de la copie vers %COPIE% ^(la sauvegarde elle-meme est faite^).
    echo === %date% %time% === ECHEC de la copie vers %COPIE% >> sauvegardes\journal.txt
    exit /b 1
  )
  echo Copie faite vers %COPIE%
)
