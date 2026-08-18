#!/usr/bin/env bash
set -euo pipefail

# Tag/branch to fetch. No tagged release exists yet — update this at the
# first tagged release (see
# docs/superpowers/specs/2026-08-18-install-sh-design.md).
REF="${REF:-main}"
REPO_URL="${REPO_URL:-git@github.com:fhelenne/UltimateMediaCenter.git}"
TARGET_DIR="${TARGET_DIR:-$HOME/ultimatemediacenter}"
DRY_RUN=0

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    *)
      echo "Usage: install.sh [--dry-run]" >&2
      exit 1
      ;;
  esac
done

LOG_FILE="${TARGET_DIR}/install.log"

log() {
  echo "$(date '+%Y-%m-%d %H:%M:%S') $*"
}

run() {
  if [ "$DRY_RUN" -eq 1 ]; then
    log "[dry-run] $*"
  else
    log "+ $*"
    "$@"
  fi
}

check_prereqs() {
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    log "Docker + plugin Compose déjà présents."
    return
  fi
  log "Docker ou le plugin Compose manquant, installation via get.docker.com..."
  if [ "$DRY_RUN" -eq 1 ]; then
    log "[dry-run] curl -fsSL https://get.docker.com | sh"
  else
    curl -fsSL https://get.docker.com | sh
  fi
}

is_existing_install() {
  [ -f "${TARGET_DIR}/.env" ]
}

fetch_release() {
  if [ -d "${TARGET_DIR}/.git" ]; then
    run git -C "$TARGET_DIR" fetch --depth 1 origin "$REF"
    run git -C "$TARGET_DIR" checkout "$REF"
    run git -C "$TARGET_DIR" reset --hard "origin/${REF}"
  else
    # TARGET_DIR already exists at this point (main() ran mkdir -p and
    # started logging into it), so it is never empty and `git clone`
    # would refuse it. Init + fetch + checkout in place instead.
    run git -C "$TARGET_DIR" init
    run git -C "$TARGET_DIR" remote add origin "$REPO_URL"
    run git -C "$TARGET_DIR" fetch --depth 1 origin "$REF"
    run git -C "$TARGET_DIR" checkout "$REF"
  fi
}

random_secret() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 32
  else
    head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n'
  fi
}

detect_usb_mount() {
  local candidate
  for candidate in /media/*/* /mnt/*; do
    if [ -d "$candidate" ] && [ -w "$candidate" ]; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

generate_env() {
  local usb_mount
  if usb_mount=$(detect_usb_mount); then
    log "Disque USB détecté automatiquement : $usb_mount"
  else
    read -r -p "Point de montage du disque USB pour la bibliothèque média : " usb_mount
  fi

  local sonarr_api_key radarr_api_key lidarr_api_key readarr_api_key
  sonarr_api_key=$(random_secret)
  radarr_api_key=$(random_secret)
  lidarr_api_key=$(random_secret)
  readarr_api_key=$(random_secret)

  sed \
    -e "s#^USB_MOUNT=.*#USB_MOUNT=${usb_mount}#" \
    -e "s#^SONARR_SECRET=.*#SONARR_SECRET=$(random_secret)#" \
    -e "s#^RADARR_SECRET=.*#RADARR_SECRET=$(random_secret)#" \
    -e "s#^LIDARR_SECRET=.*#LIDARR_SECRET=$(random_secret)#" \
    -e "s#^READARR_SECRET=.*#READARR_SECRET=$(random_secret)#" \
    -e "s#^SONARR_API_KEY=.*#SONARR_API_KEY=${sonarr_api_key}#" \
    -e "s#^RADARR_API_KEY=.*#RADARR_API_KEY=${radarr_api_key}#" \
    -e "s#^LIDARR_API_KEY=.*#LIDARR_API_KEY=${lidarr_api_key}#" \
    -e "s#^READARR_API_KEY=.*#READARR_API_KEY=${readarr_api_key}#" \
    -e "s#^SESSION_SECRET=.*#SESSION_SECRET=$(random_secret)#" \
    "${TARGET_DIR}/.env.example" > "${TARGET_DIR}/.env"

  mkdir -p "${usb_mount}/tv" "${usb_mount}/movies" "${usb_mount}/music" "${usb_mount}/books-library"

  log "Fichier .env généré, secrets et clés API *arr aléatoires écrits."
}

seed_arr_configs() {
  local service port api_key volume
  for service in sonarr radarr lidarr readarr; do
    case "$service" in
      sonarr) port=8989 ;;
      radarr) port=7878 ;;
      lidarr) port=8686 ;;
      readarr) port=8787 ;;
    esac
    api_key=$(grep "^${service^^}_API_KEY=" "${TARGET_DIR}/.env" | cut -d= -f2)
    volume="ultimatemediacenter_${service}-config"
    run docker volume create "$volume" >/dev/null
    run docker run --rm -v "${volume}:/config" alpine sh -c "
      if [ ! -f /config/config.xml ]; then
        cat > /config/config.xml <<EOF
<Config>
  <LogLevel>info</LogLevel>
  <Port>${port}</Port>
  <ApiKey>${api_key}</ApiKey>
</Config>
EOF
      fi
    "
  done
  log "Clés API pré-semées dans les config.xml de sonarr/radarr/lidarr/readarr."
}

main() {
  mkdir -p "$TARGET_DIR"
  exec > >(tee -a "$LOG_FILE") 2>&1
  if [ "$REF" = "main" ]; then
    log "ATTENTION : aucune release taguée disponible, utilisation de la branche main."
  fi
  check_prereqs
  if is_existing_install; then
    log "Installation existante détectée (.env présent) — mode mise à jour."
    FRESH_INSTALL=0
  else
    log "Aucune installation existante détectée — installation fraîche."
    FRESH_INSTALL=1
  fi
  fetch_release
  if [ "$FRESH_INSTALL" -eq 1 ]; then
    generate_env
    seed_arr_configs
  fi
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  main "$@"
fi
