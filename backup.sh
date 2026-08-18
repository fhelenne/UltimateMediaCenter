#!/usr/bin/env bash
set -euo pipefail

RCLONE_REMOTE="${RCLONE_REMOTE:-}"
RCLONE_CONFIG_DIR="${RCLONE_CONFIG_DIR:-$HOME/.config/rclone}"
TARGET_DIR="${TARGET_DIR:-$HOME/ultimatemediacenter}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
LOG_FILE="${TARGET_DIR}/backup.log"
RCLONE_EXTRA_MOUNTS=()
work_dir=""

VOLUMES=(sonarr-config radarr-config lidarr-config readarr-config jellyfin-config calibre-web-config app-data)

log() {
  echo "$(date '+%Y-%m-%d %H:%M:%S') $*"
}

rclone() {
  docker run --rm -v "${RCLONE_CONFIG_DIR}:/config/rclone" "${RCLONE_EXTRA_MOUNTS[@]}" \
    rclone/rclone "$@"
}

check_prereqs() {
  if [ -z "$RCLONE_REMOTE" ]; then
    log "ERREUR : RCLONE_REMOTE non défini. Configurer un remote avec 'docker run --rm -it -v \$HOME/.config/rclone:/config/rclone rclone/rclone config' puis exporter RCLONE_REMOTE=nom:chemin."
    exit 1
  fi
  if ! command -v docker >/dev/null 2>&1; then
    log "ERREUR : commande 'docker' introuvable dans PATH."
    exit 1
  fi
}

archive_volumes() {
  local work_dir="$1"
  local vol full_vol
  for vol in "${VOLUMES[@]}"; do
    full_vol="ultimatemediacenter_${vol}"
    log "Archivage du volume ${full_vol}..."
    docker run --rm -v "${full_vol}:/data:ro" -v "${work_dir}:/backup" alpine \
      tar czf "/backup/${vol}.tar.gz" -C /data .
  done
}

push_backup() {
  local work_dir="$1"
  local dest="${RCLONE_REMOTE}/$(date +%Y-%m-%d)/"
  log "Envoi vers ${dest}..."
  RCLONE_EXTRA_MOUNTS=(-v "${work_dir}:/data")
  if [[ "$RCLONE_REMOTE" == /* ]]; then
    RCLONE_EXTRA_MOUNTS+=(-v "${RCLONE_REMOTE}:${RCLONE_REMOTE}")
  fi
  rclone copy /data "$dest"
  RCLONE_EXTRA_MOUNTS=()
}

prune_old_backups() {
  local cutoff entry
  cutoff="$(date -d "-${RETENTION_DAYS} days" +%Y-%m-%d)"
  if [[ "$RCLONE_REMOTE" == /* ]]; then
    RCLONE_EXTRA_MOUNTS=(-v "${RCLONE_REMOTE}:${RCLONE_REMOTE}")
  fi
  rclone lsf "$RCLONE_REMOTE" --dirs-only 2>/dev/null | while read -r entry; do
    entry="${entry%/}"
    if [[ "$entry" < "$cutoff" ]]; then
      log "Suppression de la sauvegarde expirée : ${entry}"
      rclone purge "${RCLONE_REMOTE}/${entry}"
    fi
  done
  RCLONE_EXTRA_MOUNTS=()
}

main() {
  mkdir -p "$TARGET_DIR"
  exec >> "$LOG_FILE" 2>&1
  log "=== Sauvegarde démarrée ==="
  check_prereqs
  work_dir="$(mktemp -d)"
  trap 'rm -rf "$work_dir"' EXIT
  archive_volumes "$work_dir"
  push_backup "$work_dir"
  prune_old_backups
  log "=== Sauvegarde terminée ==="
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  main "$@"
fi
