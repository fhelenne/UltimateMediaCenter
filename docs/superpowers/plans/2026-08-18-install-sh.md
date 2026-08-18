# install.sh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A one-liner `install.sh` that takes a vanilla Raspberry Pi OS
64-bit install to a running UltimateMediaCenter stack (app, *arr, Jellyfin,
Calibre-web, Caddy, ntfy) with exactly one interactive prompt (USB mount
path), plus the `docker-compose.yml` fixes it depends on (missing
`jellyfin` service, media volumes not bound to the USB disk).

**Architecture:** `install.sh` is a single bash script built as small
testable functions (`check_prereqs`, `is_existing_install`, `fetch_release`,
`generate_env`, `seed_arr_configs`, `up`, `summary`), wired together in
`main()`. Each function is independently runnable against a scratch
directory for verification — no Pi hardware needed to validate the logic,
only Docker (available in this environment) and `shellcheck`. `docker-compose.yml`
gets a pinned project name (so pre-seeded volume names are deterministic),
a `jellyfin` service, and `driver_opts` bind mounts on the media volumes.

**Tech Stack:** bash (`set -euo pipefail`), Docker + Compose plugin, `git`,
`openssl` (secret generation, with a `/dev/urandom` fallback), `shellcheck`
for linting (run via `docker run koalaman/shellcheck` — not installed
locally).

**Spec:** `docs/superpowers/specs/2026-08-18-install-sh-design.md`

## Global Constraints

- No git tags exist yet — `REF` defaults to `"main"` with a loud warning;
  fixing the release pipeline itself is out of scope for this plan
- `install.sh` must work with exactly one interactive prompt (USB mount
  path), and only when auto-detection fails
- No new Python dependency, no change to `app/` — this plan is pure
  ops/infra
- `uninstall.sh` is explicitly out of scope (spec: "nice to have, not v1")
- The *arr network/auth model (ports exposed directly on the host) is
  pre-existing and must not be silently redesigned by this plan

---

### Task 1: `docker-compose.yml` — pin project name, add `jellyfin`, bind media volumes to USB

**Files:**
- Modify: `docker-compose.yml`
- Modify: `.env.example`

**Interfaces:**
- Produces: a `${USB_MOUNT}` variable (read from `.env` at the repo root,
  which Compose auto-interpolates into the YAML) that Task 4's
  `generate_env` will populate; a `jellyfin` service and a `jellyfin-config`
  volume; a pinned Compose project name `ultimatemediacenter`, which Task 5's
  `seed_arr_configs` depends on for deterministic volume names
  (`ultimatemediacenter_sonarr-config`, etc.)

- [ ] **Step 1: Pin the Compose project name**

At the very top of `docker-compose.yml`, before the `services:` key, add:

```yaml
name: ultimatemediacenter

services:
```

- [ ] **Step 2: Add the `jellyfin` service**

Add this service block (alphabetically after `caddy`, before `ntfy`, to
match the file's existing ordering):

```yaml
  jellyfin:
    image: linuxserver/jellyfin:latest
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=Europe/Paris
    ports:
      - "8096:8096"
    volumes:
      - jellyfin-config:/config
      - sonarr-tv:/data/tv:ro
      - radarr-movies:/data/movies:ro
      - lidarr-music:/data/music:ro
      - books-library:/data/books:ro
    restart: unless-stopped
```

- [ ] **Step 3: Bind media volumes to the USB mount**

Replace the `volumes:` top-level block (currently a flat list of bare
volume names) with:

```yaml
volumes:
  app-data:
  ntfy-data:
  ntfy-etc:
  sonarr-config:
  sonarr-tv:
    driver_opts:
      type: none
      o: bind
      device: ${USB_MOUNT}/tv
  sonarr-downloads:
  radarr-config:
  radarr-movies:
    driver_opts:
      type: none
      o: bind
      device: ${USB_MOUNT}/movies
  radarr-downloads:
  lidarr-config:
  lidarr-music:
    driver_opts:
      type: none
      o: bind
      device: ${USB_MOUNT}/music
  lidarr-downloads:
  readarr-config:
  readarr-books:
  readarr-downloads:
  books-library:
    driver_opts:
      type: none
      o: bind
      device: ${USB_MOUNT}/books-library
  calibre-web-config:
  caddy-data:
  jellyfin-config:
```

`readarr-books` (Readarr's own working/download dir, distinct from the
shared `books-library` — see the docker-compose comment history from Phase
5a) stays a regular Docker-managed volume, not bound to the USB disk;
only the volumes holding the actual finished media library get bound.

- [ ] **Step 4: Document `USB_MOUNT` in `.env.example`**

Add near the top of `.env.example`, before `NTFY_URL=...`:

```
# Chemin du point de montage du disque USB externe sur l'hôte — utilisé
# uniquement par docker-compose.yml (driver_opts bind mount des volumes
# média), jamais lu par l'appli Python elle-même.
USB_MOUNT=/media/pi/external-disk
```

- [ ] **Step 5: Verify the compose file parses**

```bash
mkdir -p /tmp/umc-usb-test/tv /tmp/umc-usb-test/movies /tmp/umc-usb-test/music /tmp/umc-usb-test/books-library
cp .env.example /tmp/umc-test.env
sed -i 's#^USB_MOUNT=.*#USB_MOUNT=/tmp/umc-usb-test#' /tmp/umc-test.env
docker compose --env-file /tmp/umc-test.env config -q
echo "exit code: $?"
rm -rf /tmp/umc-usb-test /tmp/umc-test.env
```

Expected: no output from `docker compose config -q`, exit code 0.

- [ ] **Step 6: Commit**

```bash
git add docker-compose.yml .env.example
git commit -m "feat: add jellyfin service, bind media volumes to USB mount"
```

---

### Task 2: `install.sh` skeleton — strict mode, logging, `--dry-run`, prereqs

**Files:**
- Create: `install.sh`

**Interfaces:**
- Produces: `run <cmd...>` (respects `$DRY_RUN`, all other functions call
  through it instead of invoking commands directly), `log <msg>`,
  `check_prereqs`, globals `$REF`, `$REPO_URL`, `$TARGET_DIR`, `$DRY_RUN`,
  `$LOG_FILE`, `main()` (calls `check_prereqs` only for now — later tasks
  extend it)

- [ ] **Step 1: Write `install.sh`**

```bash
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
```

This guard matters beyond style: later tasks' verification steps
`source install.sh` to get the function definitions in isolation without
running the real `main` (which would otherwise attempt a live `git clone`
against `$REPO_URL` and block/fail). Without the guard, sourcing the
script always runs `main "$@"` for real.

- [ ] **Step 2: Make it executable**

```bash
chmod +x install.sh
```

- [ ] **Step 3: Verify**

```bash
rm -rf /tmp/umc-install-test
TARGET_DIR=/tmp/umc-install-test ./install.sh --dry-run
echo "exit code: $?"
grep -q "Docker" /tmp/umc-install-test/install.log
echo "log ok"
rm -rf /tmp/umc-install-test
```

Expected: exit code 0, `install.log` created under the target dir and
containing a line mentioning Docker.

- [ ] **Step 4: Commit**

```bash
git add install.sh
git commit -m "feat: add install.sh skeleton (logging, dry-run, prereqs check)"
```

---

### Task 3: `install.sh` — `is_existing_install` + `fetch_release`

**Files:**
- Modify: `install.sh`

**Interfaces:**
- Consumes: `$TARGET_DIR`, `$REF`, `$REPO_URL`, `run`, `log` (Task 2)
- Produces: `is_existing_install` (returns 0/1 via exit status), `fetch_release`

- [ ] **Step 1: Add `is_existing_install` and `fetch_release`**

Insert these two functions above `main()` in `install.sh`:

```bash
is_existing_install() {
  [ -f "${TARGET_DIR}/.env" ]
}

fetch_release() {
  if [ -d "${TARGET_DIR}/.git" ]; then
    run git -C "$TARGET_DIR" fetch --depth 1 origin "$REF"
    run git -C "$TARGET_DIR" checkout "$REF"
    run git -C "$TARGET_DIR" reset --hard "origin/${REF}"
  else
    run git clone --branch "$REF" --depth 1 "$REPO_URL" "$TARGET_DIR"
  fi
}
```

- [ ] **Step 2: Wire into `main()`**

Replace `main()`'s body:

```bash
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
}
```

- [ ] **Step 3: Verify against a local repo (no network needed)**

```bash
rm -rf /tmp/umc-install-test
REPO_URL="file://$(pwd)" REF="main" TARGET_DIR=/tmp/umc-install-test ./install.sh
echo "exit code: $?"
test -f /tmp/umc-install-test/docker-compose.yml
echo "clone ok"

# second run should take the update path (git fetch/reset), not re-clone
touch /tmp/umc-install-test/.env
REPO_URL="file://$(pwd)" REF="main" TARGET_DIR=/tmp/umc-install-test ./install.sh
echo "exit code: $?"
grep -q "mode mise à jour" /tmp/umc-install-test/install.log
echo "update-path ok"
rm -rf /tmp/umc-install-test
```

Expected: both runs exit 0; the second run's log shows the "mode mise à
jour" line, proving `is_existing_install` correctly detected the `.env`
file and `fetch_release` took the `git fetch`/`reset` path instead of
`git clone`.

- [ ] **Step 4: Commit**

```bash
git add install.sh
git commit -m "feat: install.sh — detect existing install, fetch release"
```

---

### Task 4: `install.sh` — `generate_env` (secrets, USB detection, `.env` write)

**Files:**
- Modify: `install.sh`

**Interfaces:**
- Consumes: `$TARGET_DIR`, `log`, `run` (Task 2); reads
  `${TARGET_DIR}/.env.example` (Task 1 adds `USB_MOUNT=` to it)
- Produces: `random_secret`, `detect_usb_mount`, `generate_env` — writes
  `${TARGET_DIR}/.env` with every `changeme`/placeholder value replaced

- [ ] **Step 1: Add `random_secret`, `detect_usb_mount`, `generate_env`**

Insert above `main()`:

```bash
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
```

- [ ] **Step 2: Wire into `main()`'s fresh-install branch**

Replace `main()`'s body:

```bash
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
  fi
}
```

- [ ] **Step 3: Verify**

```bash
rm -rf /tmp/umc-install-test
mkdir -p /tmp/umc-install-test
cp .env.example /tmp/umc-install-test/.env.example
mkdir -p /tmp/umc-usb-fake
TARGET_DIR=/tmp/umc-install-test bash -c '
  source install.sh
  TARGET_DIR=/tmp/umc-install-test
  detect_usb_mount() { echo /tmp/umc-usb-fake; }
  generate_env
'
grep -q "^SESSION_SECRET=" /tmp/umc-install-test/.env
! grep -q "changeme" /tmp/umc-install-test/.env
grep -q "^USB_MOUNT=/tmp/umc-usb-fake$" /tmp/umc-install-test/.env
test -d /tmp/umc-usb-fake/tv
echo "generate_env ok"
rm -rf /tmp/umc-install-test /tmp/umc-usb-fake
```

Expected: no `changeme` string anywhere in the generated `.env`,
`USB_MOUNT` set to the fake path, and `/tmp/umc-usb-fake/tv` created.

- [ ] **Step 4: Commit**

```bash
git add install.sh
git commit -m "feat: install.sh — generate .env secrets, detect USB mount"
```

---

### Task 5: `install.sh` — `seed_arr_configs`

**Files:**
- Modify: `install.sh`

**Interfaces:**
- Consumes: `$TARGET_DIR`, `run`, `log` (Task 2); the *arr API keys
  generated in Task 4's `generate_env` (read back from `.env` rather than
  passed as variables, since they're separate function invocations in `main()`)
- Produces: `seed_arr_configs` — writes a minimal `config.xml` into each
  *arr's named Docker volume before first boot

- [ ] **Step 1: Add `seed_arr_configs`**

Insert above `main()`:

```bash
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
```

- [ ] **Step 2: Wire into `main()`'s fresh-install branch**

Replace `main()`'s body:

```bash
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
```

- [ ] **Step 3: Verify against real Docker**

```bash
rm -rf /tmp/umc-install-test
mkdir -p /tmp/umc-install-test
printf 'SONARR_API_KEY=testkey123\nRADARR_API_KEY=testkey456\nLIDARR_API_KEY=testkey789\nREADARR_API_KEY=testkeyabc\n' > /tmp/umc-install-test/.env
TARGET_DIR=/tmp/umc-install-test bash -c '
  source install.sh
  TARGET_DIR=/tmp/umc-install-test
  seed_arr_configs
'
docker run --rm -v ultimatemediacenter_sonarr-config:/config alpine cat /config/config.xml | grep -q "testkey123"
echo "sonarr seeded ok"
docker run --rm -v ultimatemediacenter_readarr-config:/config alpine cat /config/config.xml | grep -q "8787"
echo "readarr port ok"

# idempotency: re-run must not clobber an existing config.xml
docker run --rm -v ultimatemediacenter_sonarr-config:/config alpine sh -c 'echo CUSTOM > /config/config.xml'
TARGET_DIR=/tmp/umc-install-test bash -c '
  source install.sh
  TARGET_DIR=/tmp/umc-install-test
  seed_arr_configs
'
docker run --rm -v ultimatemediacenter_sonarr-config:/config alpine cat /config/config.xml | grep -q "CUSTOM"
echo "idempotency ok"

docker volume rm ultimatemediacenter_sonarr-config ultimatemediacenter_radarr-config ultimatemediacenter_lidarr-config ultimatemediacenter_readarr-config
rm -rf /tmp/umc-install-test
```

Expected: each *arr's `config.xml` contains the right API key and port;
the idempotency check proves a pre-existing `config.xml` is never
overwritten.

- [ ] **Step 4: Commit**

```bash
git add install.sh
git commit -m "feat: install.sh — pre-seed *arr config.xml with generated API keys"
```

---

### Task 6: `install.sh` — `up`, `summary`, full wiring

**Files:**
- Modify: `install.sh`

**Interfaces:**
- Consumes: everything from Tasks 2-5
- Produces: `up`, `summary`, final `main()`

- [ ] **Step 1: Make `generate_env` dry-run-safe (no blocking prompt)**

`generate_env` (Task 4) calls `read -r -p ...` when `detect_usb_mount`
fails — this would block forever under `--dry-run`. Modify the start of
`generate_env` in `install.sh`:

```bash
generate_env() {
  local usb_mount
  if usb_mount=$(detect_usb_mount); then
    log "Disque USB détecté automatiquement : $usb_mount"
  elif [ "$DRY_RUN" -eq 1 ]; then
    usb_mount=/tmp/dry-run-usb
    log "[dry-run] pas de point de montage détecté, valeur fictive utilisée : $usb_mount"
  else
    read -r -p "Point de montage du disque USB pour la bibliothèque média : " usb_mount
  fi
```

(The rest of the function body — the `sonarr_api_key=...` block onward —
is unchanged from Task 4.)

- [ ] **Step 2: Add `up` and `summary`**

Insert above `main()`:

```bash
up() {
  run docker compose --project-directory "$TARGET_DIR" pull
  run docker compose --project-directory "$TARGET_DIR" up -d
}

summary() {
  local admin_password url
  url="http://$(hostname -I 2>/dev/null | awk '{print $1}'):8000"
  log ""
  log "Installation terminée."
  log "URL locale : ${url}"
  if [ "$DRY_RUN" -eq 0 ]; then
    admin_password=$(docker compose --project-directory "$TARGET_DIR" logs app 2>/dev/null \
      | grep -o "mot de passe initial: [^ ]*" | tail -n1 | cut -d' ' -f4 || true)
    if [ -n "$admin_password" ]; then
      log "Mot de passe admin initial : ${admin_password}"
      log "(changement obligatoire à la première connexion)"
    fi
  fi
  log "Configuration liseuse Kobo : voir docs/user/liseuse-kobo.md"
}
```

- [ ] **Step 3: Finalize `main()`**

Replace `main()`'s body:

```bash
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
  up
  summary
}
```

- [ ] **Step 4: Verify the full flow end-to-end in dry-run**

```bash
rm -rf /tmp/umc-install-test
REPO_URL="file://$(pwd)" REF="main" TARGET_DIR=/tmp/umc-install-test ./install.sh --dry-run
echo "exit code: $?"
grep -q "installation fraîche" /tmp/umc-install-test/install.log
grep -q "\[dry-run\] docker compose" /tmp/umc-install-test/install.log
rm -rf /tmp/umc-install-test
```

Expected: exit code 0, log shows the fresh-install path taken, the
dry-run-safe USB fallback from Step 1 firing instead of blocking on
`read`, and the `up()` docker compose calls logged as dry-run rather than
actually executed.

- [ ] **Step 5: Commit**

```bash
git add install.sh
git commit -m "feat: install.sh — docker compose up, summary, full wiring"
```

---

### Task 7: Lint, docs propagation, dev plan

**Files:**
- Modify: `.ai/05-DEPLOYMENT.md`
- Modify: `.ai/DEVELOPMENT_PLAN.md`

**Interfaces:**
- Consumes: nothing
- Produces: nothing

- [ ] **Step 1: Run shellcheck**

```bash
docker run --rm -v "$(pwd):/mnt" -w /mnt koalaman/shellcheck:stable install.sh
```

Expected: no errors. Fix anything shellcheck flags (most likely: quoting
around `$candidate` in `detect_usb_mount`'s glob loop, or `local` usage
inside `case` — adjust in `install.sh` directly, no plan step needed for
specific fixes since they depend on shellcheck's actual output).

- [ ] **Step 2: Update `.ai/05-DEPLOYMENT.md`**

In the "Installation en une commande" section, after the existing
numbered list, add:

```markdown
Détails d'implémentation :
- Les clés API *arr sont pré-semées dans le `config.xml` de chaque service
  (dans son volume Docker, avant premier démarrage) plutôt que copiées
  manuellement depuis chaque interface — zéro étape manuelle supplémentaire
- `install.sh --dry-run` affiche toutes les actions sans toucher à Docker
  ni au réseau — utile pour relire le script avant de l'exécuter pour de vrai
- `REF` (branche/tag ciblé par `install.sh`) vaut `main` tant qu'aucune
  release taguée n'existe — dette assumée, à corriger dès la première
  release (cf. `docs/superpowers/specs/2026-08-18-install-sh-design.md`)
```

- [ ] **Step 3: Update checkbox**

In `.ai/DEVELOPMENT_PLAN.md`, under `## Phase 6 — Durcissement`:

```markdown
- [x] Script d'installation one-liner (`install.sh`), idempotent, testé sur
      Raspberry Pi OS vierge — cf. `05-DEPLOYMENT.md`
```

(Testing "on a real vierge Pi" is not literally done — see the spec's
"Ce que cette vérification ne couvre pas" section. Checking this box
reflects the script being complete and locally verified; a manual
real-hardware pass remains recommended before the first tagged release,
noted in the spec, not re-litigated here.)

- [ ] **Step 4: Commit**

```bash
git add .ai/05-DEPLOYMENT.md .ai/DEVELOPMENT_PLAN.md
git commit -m "docs: mark install.sh done, document implementation details"
```
