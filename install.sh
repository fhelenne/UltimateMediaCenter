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

main() {
  mkdir -p "$TARGET_DIR"
  exec > >(tee -a "$LOG_FILE") 2>&1
  if [ "$REF" = "main" ]; then
    log "ATTENTION : aucune release taguée disponible, utilisation de la branche main."
  fi
  check_prereqs
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  main "$@"
fi
