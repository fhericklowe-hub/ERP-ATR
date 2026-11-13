#!/bin/sh
# Sauvegarde et restauration de l'ERP : la base PostgreSQL et le dossier des pieces jointes.
# Lance dans le conteneur « sauvegarde » (voir docker-compose.yml), le plus souvent par sauvegarder.bat et restaurer.bat.
#
#   sauvegarde.sh sauvegarder            une sauvegarde datee, puis menage des plus anciennes
#   sauvegarde.sh lister                 les sauvegardes disponibles
#   sauvegarde.sh restaurer AAAAMMJJ-HHMMSS --oui     remet la base et les pieces jointes de cette date
set -eu

DOSSIER="${DOSSIER_SAUVEGARDES:-/sauvegardes}"
MEDIA="${MEDIA_ROOT:-/data/media}"
GARDER="${SAUVEGARDES_JOURS:-30}"

erreur() { echo "ERREUR : $*" >&2; exit 1; }
taille() { du -h "$1" | cut -f1; }

lister() {
  trouve=0
  for f in "$DOSSIER"/erp-*.dump; do
    [ -e "$f" ] || continue
    trouve=1
    nom="$(basename "$f" .dump)"
    echo "${nom#erp-}  base $(taille "$f")"
  done
  [ "$trouve" = 1 ] || echo "Aucune sauvegarde dans $DOSSIER."
}

sauvegarder() {
  case "$GARDER" in ''|*[!0-9]*|0) erreur "SAUVEGARDES_JOURS doit etre un nombre de jours, 1 au moins (valeur lue : '$GARDER')." ;; esac
  mkdir -p "$DOSSIER"
  horodatage="$(date +%Y%m%d-%H%M%S)"
  base="$DOSSIER/erp-$horodatage.dump"
  pieces="$DOSSIER/media-$horodatage.tar.gz"
  provisoire_base="$DOSSIER/.erp-$horodatage.tmp"
  provisoire_pieces="$DOSSIER/.media-$horodatage.tmp"
  # On ecrit dans un fichier provisoire : une sauvegarde interrompue ne ressemble jamais a une sauvegarde valide.
  trap 'rm -f "$provisoire_base" "$provisoire_pieces"' EXIT

  pg_dump --format=custom --no-owner --file "$provisoire_base"
  pg_restore --list "$provisoire_base" >/dev/null || erreur "la sauvegarde de la base n'est pas lisible."
  mv "$provisoire_base" "$base"
  echo "Base sauvegardee : $base ($(taille "$base"))"

  if [ -d "$MEDIA" ] && [ -n "$(ls -A "$MEDIA" 2>/dev/null)" ]; then
    tar czf "$provisoire_pieces" -C "$MEDIA" .
    tar tzf "$provisoire_pieces" >/dev/null || erreur "la sauvegarde des pieces jointes n'est pas lisible."
    mv "$provisoire_pieces" "$pieces"
    echo "Pieces jointes sauvegardees : $pieces ($(taille "$pieces"))"
  else
    echo "Aucune piece jointe a sauvegarder."
  fi

  # Menage : seulement apres une sauvegarde reussie, et jamais celle qui vient d'etre faite.
  find "$DOSSIER" -maxdepth 1 \( -name 'erp-*.dump' -o -name 'media-*.tar.gz' \) -mtime +"$GARDER" ! -name "*-$horodatage.*" -delete
  echo "Sauvegardes gardees $GARDER jours. Termine : $horodatage"
}

restaurer() {
  horodatage="${1:-}"
  [ -n "$horodatage" ] || { lister; erreur "indiquez la date de la sauvegarde a restaurer."; }
  case "$horodatage" in *[!0-9-]*) erreur "date de sauvegarde invalide : $horodatage" ;; esac
  base="$DOSSIER/erp-$horodatage.dump"
  pieces="$DOSSIER/media-$horodatage.tar.gz"
  [ -f "$base" ] || { lister; erreur "pas de sauvegarde de la base a la date $horodatage."; }
  [ "${2:-}" = "--oui" ] || erreur "la restauration remplace les donnees actuelles : confirmez avec --oui."
  pg_restore --list "$base" >/dev/null || erreur "la sauvegarde de la base n'est pas lisible : rien n'a ete restaure."
  if [ -f "$pieces" ]; then tar tzf "$pieces" >/dev/null || erreur "la sauvegarde des pieces jointes n'est pas lisible : rien n'a ete restaure."; fi

  # Tout ou rien : en cas d'echec, la base reste comme avant.
  pg_restore --single-transaction --clean --if-exists --no-owner --no-privileges --dbname "$PGDATABASE" "$base"
  echo "Base restauree depuis $base"
  if [ -f "$pieces" ]; then
    mkdir -p "$MEDIA"
    tar xzf "$pieces" -C "$MEDIA"
    echo "Pieces jointes restaurees depuis $pieces"
  else
    echo "Pas de sauvegarde des pieces jointes a cette date : celles qui sont sur le serveur sont laissees telles quelles."
  fi
}

commande="${1:-sauvegarder}"
[ $# -eq 0 ] || shift
case "$commande" in
  sauvegarder) sauvegarder ;;
  lister) lister ;;
  restaurer) restaurer "$@" ;;
  *) erreur "commande inconnue : $commande (sauvegarder, lister, restaurer)." ;;
esac
