#!/usr/bin/env bash
set -euo pipefail

# Tag/branch to fetch. No tagged release exists yet — update this at the
# first tagged release (see
# docs/superpowers/specs/2026-08-18-install-sh-design.md).
# NOTE: once REF is ever set to a real tag, `git fetch --depth 1 origin
# <tag>` does not produce a ref that `git checkout <tag>` can resolve
# directly — DWIM checkout-by-name only works for branches, not tags.
# This is a known gap for whenever REF is first set to a real release tag;
# not fixed now since no tags exist yet.
REF="${REF:-main}"
REPO_URL="${REPO_URL:-https://github.com/fhelenne/UltimateMediaCenter.git}"
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

# fd 3 keeps a handle on the real terminal so log() can still print step
# messages after main() redirects stdout/stderr into the log file — this
# is what keeps the install quiet (raw command output goes to the file
# only) while step messages and the final summary still show live.
exec 3>&1

log() {
  local msg
  msg="$(date '+%Y-%m-%d %H:%M:%S') $*"
  echo "$msg" >&3
  echo "$msg"
}

run() {
  if [ "$DRY_RUN" -eq 1 ]; then
    log "[dry-run] $*"
  else
    echo "$(date '+%Y-%m-%d %H:%M:%S') + $*"
    "$@"
  fi
}

check_prereqs() {
  local missing=""
  command -v git >/dev/null 2>&1 || missing="${missing}git "
  command -v curl >/dev/null 2>&1 || missing="${missing}curl "
  if [ -n "$missing" ]; then
    log "ERREUR : outil(s) manquant(s) requis pour l'installation : ${missing}"
    exit 1
  fi

  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    log "Docker + plugin Compose déjà présents."
    return
  fi
  log "Docker ou le plugin Compose manquant, installation via get.docker.com..."
  if [ "$DRY_RUN" -eq 1 ]; then
    log "[dry-run] curl -fsSL https://get.docker.com | sh"
  else
    curl -fsSL https://get.docker.com | sh
    if ! docker info >/dev/null 2>&1; then
      log "Docker vient d'être installé mais nécessite une reconnexion pour que les permissions prennent effet. Déconnectez-vous et reconnectez-vous (ou exécutez 'newgrp docker'), puis relancez ce script."
      exit 1
    fi
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
    if [ -d "$candidate" ] && [ -w "$candidate" ] && mountpoint -q "$candidate"; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

generate_env() {
  if [ "$DRY_RUN" -eq 1 ]; then
    log "[dry-run] generate_env: aurait généré .env et pré-semé les répertoires USB"
    return
  fi

  local usb_mount
  if usb_mount=$(detect_usb_mount); then
    log "Disque USB détecté automatiquement : $usb_mount"
    local confirm
    read -r -p "Utiliser ce point de montage ? [O/n] " confirm < /dev/tty
    if [ "$confirm" = "n" ] || [ "$confirm" = "N" ]; then
      read -r -p "Point de montage du disque USB pour la bibliothèque média : " usb_mount < /dev/tty
    fi
  else
    read -r -p "Point de montage du disque USB pour la bibliothèque média : " usb_mount < /dev/tty
  fi

  local host_library_root
  read -r -p "Dossier racine pour les bibliothèques ajoutées depuis l'UI (défaut : \$HOME) : " host_library_root < /dev/tty
  host_library_root="${host_library_root:-$HOME}"

  local sonarr_api_key radarr_api_key lidarr_api_key readarr_api_key
  sonarr_api_key=$(random_secret)
  radarr_api_key=$(random_secret)
  lidarr_api_key=$(random_secret)
  readarr_api_key=$(random_secret)

  sed \
    -e "s#^USB_MOUNT=.*#USB_MOUNT=${usb_mount}#" \
    -e "s#^HOST_LIBRARY_ROOT=.*#HOST_LIBRARY_ROOT=${host_library_root}#" \
    -e "s#^SHARES_MOUNT=.*#SHARES_MOUNT=${TARGET_DIR}/shares#" \
    -e "s#^SONARR_SECRET=.*#SONARR_SECRET=$(random_secret)#" \
    -e "s#^RADARR_SECRET=.*#RADARR_SECRET=$(random_secret)#" \
    -e "s#^LIDARR_SECRET=.*#LIDARR_SECRET=$(random_secret)#" \
    -e "s#^READARR_SECRET=.*#READARR_SECRET=$(random_secret)#" \
    -e "s#^SONARR_API_KEY=.*#SONARR_API_KEY=${sonarr_api_key}#" \
    -e "s#^RADARR_API_KEY=.*#RADARR_API_KEY=${radarr_api_key}#" \
    -e "s#^LIDARR_API_KEY=.*#LIDARR_API_KEY=${lidarr_api_key}#" \
    -e "s#^READARR_API_KEY=.*#READARR_API_KEY=${readarr_api_key}#" \
    -e "s#^SESSION_SECRET=.*#SESSION_SECRET=$(random_secret)#" \
    "${TARGET_DIR}/.env.example" > "${TARGET_DIR}/.env.tmp"
  mv "${TARGET_DIR}/.env.tmp" "${TARGET_DIR}/.env"

  mkdir -p "${usb_mount}/tv" "${usb_mount}/movies" "${usb_mount}/music" "${usb_mount}/books-library"
  mkdir -p "${TARGET_DIR}/shares"

  log "Fichier .env généré, secrets et clés API *arr aléatoires écrits."
}

seed_arr_configs() {
  if [ "$DRY_RUN" -eq 1 ]; then
    log "[dry-run] seed_arr_configs: aurait pré-semé les config.xml *arr"
    return
  fi

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
    run docker run --rm -e API_KEY="${api_key}" -e PORT="${port}" -v "${volume}:/config" alpine sh -c '
      if [ ! -f /config/config.xml ]; then
        cat > /config/config.xml <<EOF
<Config>
  <LogLevel>info</LogLevel>
  <Port>$PORT</Port>
  <ApiKey>$API_KEY</ApiKey>
</Config>
EOF
      fi
    '
  done
  log "Clés API pré-semées dans les config.xml de sonarr/radarr/lidarr/readarr."
}

check_usb_binding() {
  local vol
  for vol in sonarr-tv radarr-movies lidarr-music books-library; do
    local full_vol="ultimatemediacenter_${vol}"
    if docker volume inspect "$full_vol" >/dev/null 2>&1; then
      local device
      device=$(docker volume inspect "$full_vol" --format '{{if .Options}}{{.Options.device}}{{end}}' 2>/dev/null || echo "")
      if [ -z "$device" ]; then
        log "ERREUR : le volume Docker '${full_vol}' existe déjà sans être lié au disque USB."
        log "Ce volume contient probablement des données sur la carte SD, pas sur le disque USB."
        log "Pour corriger : sauvegardez son contenu si besoin, puis 'docker volume rm ${full_vol}' avant de relancer ce script."
        exit 1
      fi
    fi
  done
}

up() {
  if [ "$DRY_RUN" -eq 0 ]; then
    check_usb_binding
  fi
  run docker compose --project-directory "$TARGET_DIR" pull
  run docker compose --project-directory "$TARGET_DIR" up -d --build
}

sync_arr_api_keys() {
  if [ "$DRY_RUN" -eq 1 ]; then
    log "[dry-run] sync_arr_api_keys: aurait resynchronisé les clés API *arr"
    return
  fi

  local service upper key current changed container _attempt
  changed=0
  for service in sonarr radarr lidarr readarr; do
    upper=$(echo "$service" | tr '[:lower:]' '[:upper:]')
    container="ultimatemediacenter-${service}-1"
    key=""
    for _attempt in $(seq 1 15); do
      key=$(docker exec "$container" grep -o '<ApiKey>[^<]*' /config/config.xml 2>/dev/null | cut -d'>' -f2 || true)
      if [ -n "$key" ]; then
        break
      fi
      sleep 2
    done
    if [ -z "$key" ]; then
      log "AVERTISSEMENT : clé API de ${service} introuvable, resynchronisation ignorée."
      continue
    fi
    current=$(grep "^${upper}_API_KEY=" "${TARGET_DIR}/.env" | cut -d= -f2)
    if [ "$current" != "$key" ]; then
      # ${service} régénère sa propre clé au premier démarrage réel et
      # écrase notre pré-semis (config.xml complété avec des champs qu'on
      # ne fournit pas) — on relit la vraie clé et on met .env à jour.
      sed -i "s#^${upper}_API_KEY=.*#${upper}_API_KEY=${key}#" "${TARGET_DIR}/.env"
      changed=1
    fi
  done

  if [ "$changed" -eq 1 ]; then
    log "Clés API *arr resynchronisées dans .env, redémarrage de l'application..."
    run docker compose --project-directory "$TARGET_DIR" restart app
  fi
}

seed_arr_webhooks() {
  if [ "$DRY_RUN" -eq 1 ]; then
    log "[dry-run] seed_arr_webhooks: aurait enregistré la connexion webhook dans chaque *arr"
    return
  fi

  # Chaque *arr n'accepte pas de header custom pour son webhook Connect —
  # seulement URL/méthode/utilisateur/mot de passe. Le secret partagé passe
  # donc par le mot de passe en Basic Auth (côté app : app/webhooks/base.py).
  local service upper api_key secret port api_version event_field existing
  for service in sonarr radarr lidarr readarr; do
    upper=$(echo "$service" | tr '[:lower:]' '[:upper:]')
    case "$service" in
      sonarr) port=8989; api_version=v3; event_field=onDownload ;;
      radarr) port=7878; api_version=v3; event_field=onDownload ;;
      lidarr) port=8686; api_version=v1; event_field=onReleaseImport ;;
      readarr) port=8787; api_version=v1; event_field=onReleaseImport ;;
    esac
    api_key=$(grep "^${upper}_API_KEY=" "${TARGET_DIR}/.env" | cut -d= -f2)
    secret=$(grep "^${upper}_SECRET=" "${TARGET_DIR}/.env" | cut -d= -f2)

    existing=$(docker run --rm --network ultimatemediacenter_default alpine sh -c "
      wget -qO- --header='X-Api-Key: ${api_key}' http://${service}:${port}/api/${api_version}/notification
    " 2>/dev/null || true)
    if echo "$existing" | grep -q '"name":"UltimateMediaCenter"'; then
      log "Webhook déjà enregistré dans ${service}, ignoré."
      continue
    fi

    run docker run --rm --network ultimatemediacenter_default alpine sh -c "
      wget -qO- --header='X-Api-Key: ${api_key}' --header='Content-Type: application/json' \
        --post-data='{\"name\":\"UltimateMediaCenter\",\"implementation\":\"Webhook\",\"configContract\":\"WebhookSettings\",\"fields\":[{\"name\":\"url\",\"value\":\"http://app:8000/webhook/${service}\"},{\"name\":\"method\",\"value\":1},{\"name\":\"username\",\"value\":\"webhook\"},{\"name\":\"password\",\"value\":\"${secret}\"}],\"${event_field}\":true,\"onGrab\":false,\"onUpgrade\":true,\"onRename\":false,\"onHealthIssue\":false,\"onApplicationUpdate\":false,\"tags\":[]}' \
        http://${service}:${port}/api/${api_version}/notification
    " >/dev/null
  done
  log "Webhooks enregistrés dans sonarr/radarr/lidarr/readarr."
}

summary() {
  local admin_password url
  url="http://$(hostname -I 2>/dev/null | awk '{print $1}'):8000"
  log ""
  log "Installation terminée."
  log "URL locale : ${url}"
  if [ "$DRY_RUN" -eq 0 ]; then
    local _attempt
    for __attempt in $(seq 1 15); do
      admin_password=$(docker compose --project-directory "$TARGET_DIR" logs app 2>/dev/null \
        | grep -o "mot de passe initial: [^ ]*" | tail -n1 | cut -d' ' -f5 || true)
      if [ -n "$admin_password" ]; then
        break
      fi
      sleep 2
    done
    if [ -n "$admin_password" ]; then
      log "Mot de passe admin initial : ${admin_password}"
      log "(changement obligatoire à la première connexion)"
    else
      log "Mot de passe admin non trouvé automatiquement — récupérez-le avec : docker compose logs app | grep 'mot de passe initial'"
    fi
  fi
  log "Configuration liseuse Kobo : voir docs/user/liseuse-kobo.md"
  log "Jellyfin nécessite une configuration manuelle initiale (assistant web) : voir le commentaire JELLYFIN_API_KEY dans .env.example"
}

main() {
  mkdir -p "$TARGET_DIR"
  umask 077
  exec >> "$LOG_FILE" 2>&1
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
  up
  if [ "$FRESH_INSTALL" -eq 1 ]; then
    sync_arr_api_keys
  fi
  seed_arr_webhooks
  summary
}

if ! (return 0 2>/dev/null); then
  main "$@"
fi
