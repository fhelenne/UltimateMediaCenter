# Phase 5a — Pipeline ebooks + pont Calibre-web

**Statut** : validé
**Date** : 2026-08-16
**Périmètre** : sous-projet de Phase 5 (Intégration lecture) — couvre le
pipeline ebooks et le pont Kobo Sync/OPDS via Calibre-web (ADR 0004).
La lecture Jellyfin dans l'UI est un sous-projet séparé, hors périmètre ici.

## Contexte

ADR 0004 a déjà tranché l'approche : Calibre-web sert uniquement de pont
protocole (`/kobo/*`, `/opds/*`), jamais d'UI visible. Le scan,
l'enrichissement et l'organisation des fichiers ebooks restent gérés par
`calibredb` / `fetch-ebook-metadata`, indépendamment de Calibre-web. Ce
document précise comment ces pièces s'assemblent concrètement.

## Architecture

Nouveau module `app/ebooks/` exécute `calibredb add` puis
`fetch-ebook-metadata` en sous-processus contre une bibliothèque Calibre
partagée. Le webhook Readarr existant (`app/webhooks/readarr.py`)
déclenche ce module sur les événements `Download` — `handle_webhook`
dans `base.py` reçoit un nouveau hook async optionnel, invoqué après la
vérification secret/Test, avant la notification ntfy, pour ne jamais
scanner sur une requête non authentifiée ou de test.

Calibre-web (nouveau service Docker) indexe la même bibliothèque en
lecture seule et sert `/kobo/*` + `/opds/*`. Caddy (nouveau service
Docker) est le seul point d'entrée réseau : il route `/kobo/*` et
`/opds/*` vers calibre-web, bloque `/web` (interface propre de
Calibre-web), et route tout le reste vers `app`.

## Composants

- **`app/ebooks/ebooks.py`** — `scan_and_enrich(path: str) -> None` :
  lance `calibredb add --library-path <lib> <path>` puis
  `fetch-ebook-metadata` pour le livre ajouté, via
  `asyncio.create_subprocess_exec`. Logue et avale les erreurs de
  sous-processus (même pattern que les échecs ntfy dans `base.py` — un
  enrichissement raté ne doit pas faire échouer le webhook).
- **`app/config.py`** — ajout du setting `calibre_library_path: str`.
- **`app/webhooks/base.py`** — `handle_webhook` gagne un paramètre
  `on_download_extra: Callable[[T], Awaitable[None]] | None = None`,
  appelé (best-effort, même pattern try/except-log que ntfy) après la
  vérification secret/Test, avant le formatage + la notification.
- **`app/webhooks/readarr.py`** — `ReadarrBookFile` gagne un champ
  `path: str` (présent dans le payload webhook Readarr) ; passe
  `lambda e: ebooks.scan_and_enrich(e.bookFiles[0].path)` comme
  `on_download_extra`.
- **`docker-compose.yml`** — ajout des services `calibre-web`
  (`lscr.io/linuxserver/calibre-web`, volume bibliothèque partagé en
  lecture seule, volume config dédié) et `caddy` ; nouveau volume
  partagé `books-library`, monté lecture-écriture dans `app` (pour
  `calibredb`) et lecture seule dans `calibre-web`.
- **`Caddyfile`** (nouveau fichier) — règles de routage décrites
  ci-dessus.

## Flux de données

Readarr télécharge un livre → POST `/webhook/readarr` (événement
Download, contient `bookFiles[0].path`) → secret validé →
`scan_and_enrich(path)` se déclenche (import calibredb + enrichissement
métadonnées contre la bibliothèque partagée) → notification ntfy
envoyée (comportement existant, inchangé) → 200 retourné. Calibre-web
réindexe la même bibliothèque selon son propre cycle (comportement
natif, aucun déclenchement côté app nécessaire) → la liseuse Kobo
synchronise via `/kobo/*`, les autres lecteurs via `/opds/*`.

## Gestion des erreurs

Les échecs de `scan_and_enrich` (calibredb absent, epub corrompu,
sous-processus en échec) sont logués et avalés — même pattern que les
échecs ntfy — pour qu'un livre cassé ne casse jamais la réponse 200/ntfy
du webhook. Pas de retry automatique : le prochain événement Download
Readarr ou une relance manuelle est le chemin de récupération (aligné
avec le pattern "trivial à corriger, pas de retry auto" de Phase 4).

Le blocage de `/web` est une vraie exigence de sécurité (ADR 0004) : il
est appliqué explicitement dans le Caddyfile, jamais délégué à
l'authentification propre de Calibre-web. À vérifier manuellement (ou
scripté) dans les étapes de vérification de `05-DEPLOYMENT.md` — hors
périmètre des tests pytest.

## Tests

- `app/ebooks/ebooks.py` — TDD, mock de
  `asyncio.create_subprocess_exec`. Cas : succès (les deux commandes
  s'exécutent dans l'ordre) ; échec calibredb (logué, pas d'exception
  levée) ; échec fetch-ebook-metadata (logué, pas d'exception levée).
- `app/webhooks/base.py` — extension des tests webhook existants :
  `on_download_extra` appelé sur Download, pas appelé sur Test, pas
  appelé si secret invalide.
- `app/webhooks/readarr.py` — test du parsing du champ `path` depuis le
  payload et de sa transmission correcte.
- Pas de couverture pytest pour le Caddyfile/docker-compose
  (configuration infra, vérifiée manuellement / documentée dans le
  guide de déploiement).

## Conséquences

- Nouveaux services `calibre-web` et `caddy` dans le docker-compose
  (impacte `05-DEPLOYMENT.md`)
- Nouveau volume partagé `books-library` entre `app`, `readarr` (en
  amont) et `calibre-web`
- `app/config.py` et `.env.example` gagnent `calibre_library_path`
- Configuration manuelle une fois sur la liseuse Kobo (changement d'URL
  de sync) reste hors périmètre de ce spec — déjà notée dans ADR 0004
  comme action utilisateur finale à documenter
