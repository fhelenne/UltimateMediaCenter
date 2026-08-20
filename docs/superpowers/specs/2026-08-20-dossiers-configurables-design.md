# Dossiers de bibliothèque configurables — Design

**ADR** : `.ai/adr/0005-dossiers-configurables-ui.md`

## Objectif
Depuis l'UI, sur chaque onglet (Séries/Films/Musique/Livres), pouvoir
ajouter/retirer un ou plusieurs dossiers de bibliothèque — dossier local
n'importe où sur l'hôte, ou partage SMB (identifiants saisis dans l'UI) —
sans réinstallation ni édition manuelle de fichier.

## Architecture

### Montage large (local)
`docker-compose.yml` : un nouveau bind mount `${HOST_LIBRARY_ROOT}` (défini
à l'install, par défaut `$HOME`) monté en lecture-écriture dans `app`,
`sonarr`, `radarr`, `lidarr`, `readarr`, `jellyfin`, au même chemin en
container : `/library-root`. Tout dossier local choisi dans l'UI doit être
un sous-chemin de `HOST_LIBRARY_ROOT` — l'UI ne montre/n'accepte que ceux-là
(pas de bind mount possible en dehors sans redémarrer le stack, limite
assumée et documentée).

### Montage SMB (`app` privilégié)
- `app` gagne : `cap_add: [SYS_ADMIN]`, `cifs-utils` dans l'image, un bind
  mount host `${SHARES_MOUNT:-/mnt/umc-shares}` avec
  `bind: { propagation: shared }`.
- Au montage d'un partage, `app` exécute `mount -t cifs //server/share
  /mnt/umc-shares/<slug> -o user=...,pass=...,uid=1000,gid=1000` en
  subprocess. Propagation `shared` → visible côté hôte → visible dans les
  autres containers qui montent aussi `${SHARES_MOUNT}` (même chemin,
  non-privilégiés).
- `sonarr/radarr/lidarr/readarr/jellyfin` montent aussi
  `${SHARES_MOUNT}:/library-root/shares` (lecture-écriture, sans
  privilège) — un partage monté apparaît donc sous
  `/library-root/shares/<slug>` dans tous les containers.

### Nouveau module `app/library/`
- `app/library/folders.py` — CRUD des dossiers enregistrés (table SQLite
  `library_folders`), et appel aux API root-folder des *arr / bibliothèque
  Jellyfin pour (dés)enregistrer un chemin.
- `app/library/shares.py` — CRUD des partages SMB (table SQLite
  `smb_shares`, mot de passe en clair — cohérent avec le reste du projet,
  documenté comme dette dans l'ADR), montage/démontage effectif via
  subprocess `mount`/`umount`, remontage de tous les partages actifs au
  démarrage de `app` (hook FastAPI lifespan).

### Schéma SQLite (même fichier que `arr_cache`/`users`, `cache.py` sert de
modèle pour `init_db`)

```sql
CREATE TABLE IF NOT EXISTS library_folders (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    arr         TEXT NOT NULL,   -- 'sonarr' | 'radarr' | 'lidarr' | 'readarr'
    path        TEXT NOT NULL,   -- chemin absolu côté container (/library-root/...)
    root_folder_id TEXT,         -- id renvoyé par l'API *arr, pour pouvoir désenregistrer
    created_at  REAL NOT NULL,
    UNIQUE(arr, path)
);

CREATE TABLE IF NOT EXISTS smb_shares (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    slug        TEXT NOT NULL UNIQUE,  -- nom de dossier sous SHARES_MOUNT
    server      TEXT NOT NULL,
    share       TEXT NOT NULL,
    username    TEXT NOT NULL,
    password    TEXT NOT NULL,
    mounted     INTEGER NOT NULL DEFAULT 0,
    created_at  REAL NOT NULL
);
```

### API *arr root-folder (réutilisée, pas réimplémentée)
- Sonarr/Radarr : `POST /api/v3/rootfolder {"path": "..."}`, `DELETE
  /api/v3/rootfolder/{id}`.
- Lidarr/Readarr : mêmes routes sous `/api/v1/rootfolder` (cf. correction
  récente : ces deux-là sont restées en v1).
- Jellyfin : `POST /Library/VirtualFolders?name=...&collectionType=...`
  avec le chemin en `paths`, `DELETE /Library/VirtualFolders?name=...`.

`app/library/folders.py` expose une fonction par *arr suivant le pattern
déjà établi dans `app/arr/*.py` (client httpx + `settings` pour URL/clé).

### Endpoints UI (`app/ui/router.py`, protégés par `require_login` comme le
reste)
- `GET /library/{arr}` — liste les dossiers enregistrés pour cet `arr`
  (fragment HTMX, affiché sous la liste dans `_tab.html`).
- `POST /library/{arr}/folders` — form `path` (chemin relatif à
  `HOST_LIBRARY_ROOT`, ou vide + `share_slug` pour utiliser un partage
  monté) → crée le bind, appelle l'API root-folder, insère en DB.
- `DELETE /library/{arr}/folders/{id}` — désenregistre côté *arr, supprime
  la ligne.
- `GET /library/shares` — liste les partages SMB (masque `password`).
- `POST /library/shares` — form `server, share, username, password, slug`
  → tente le mount, si succès insère `mounted=1`.
- `DELETE /library/shares/{id}` — démonte (`umount`), supprime la ligne.
  Refuse (400) si le partage est encore référencé par un `library_folders`.

Chemins d'erreur : mount CIFS qui échoue (mauvais identifiants, serveur
injoignable) → message d'erreur HTMX inline, rien n'est inséré en DB.
Enregistrement root-folder qui échoue après un mount réussi → le mount
reste (récupérable), la ligne `library_folders` n'est pas créée, message
d'erreur affiché.

### Démarrage (`app/main.py` lifespan)
Ajout d'une étape : lire tous les `smb_shares` où `mounted=1`, retenter le
mount de chacun (best-effort, log une erreur par échec sans bloquer le
démarrage de l'app).

## Export / Import de configuration

Objectif : sauvegarder/restaurer toute la config pilotée par l'app —
`.env` (URLs, clés API *arr, secrets webhook, Jellyfin, ntfy) +
`library_folders` + `smb_shares` — en un fichier JSON portable, réimportable
sur la même install ou une autre. **Exclu explicitement** : la table
`users` (compte admin) — un import ne doit jamais pouvoir modifier ou
invalider les identifiants de connexion en place, pour ne pas risquer de
verrouiller l'accès.

### Format
```json
{
  "version": 1,
  "exported_at": "2026-08-20T20:00:00Z",
  "env": {
    "SONARR_URL": "...", "SONARR_API_KEY": "...", "SONARR_SECRET": "...",
    "RADARR_URL": "...", "...": "...",
    "JELLYFIN_URL": "...", "JELLYFIN_API_KEY": "...",
    "NTFY_URL": "...", "NTFY_TOPIC": "..."
  },
  "library_folders": [{"arr": "sonarr", "path": "/library-root/..."}],
  "smb_shares": [{"slug": "...", "server": "...", "share": "...", "username": "...", "password": "..."}]
}
```
`SESSION_SECRET` et `USB_MOUNT`/`HOST_LIBRARY_ROOT`/`SHARES_MOUNT` (chemins
propres à *cette* machine) sont exclus de l'export — les réimporter tels
quels sur une autre install n'aurait pas de sens ou casserait les mounts
locaux.

### Endpoints (`app/ui/router.py` ou nouveau `app/settings/router.py`,
`require_login`)
- `GET /settings/export` — génère le JSON ci-dessus, `Content-Disposition:
  attachment`. Avertissement affiché dans l'UI juste avant le téléchargement :
  "contient des mots de passe en clair (clés API, identifiants SMB) —
  à stocker en lieu sûr".
- `POST /settings/import` — upload du fichier JSON.
  1. Valide `version` (rejette si inconnue).
  2. Réécrit `.env` (mêmes clés que `env`, pattern temp-file-puis-`mv`
     déjà utilisé par `install.sh generate_env`) — ne touche jamais
     `SESSION_SECRET`/`USB_MOUNT`/`HOST_LIBRARY_ROOT`/`SHARES_MOUNT`.
  3. Vide et recharge `library_folders`/`smb_shares` : réenregistre chaque
     dossier via l'API root-folder du *arr concerné, remonte chaque partage
     SMB — mêmes fonctions que la création normale (`app/library/*.py`),
     donc mêmes erreurs gérées à l'identique (échec = ligne ignorée,
     rapportée dans la réponse, pas d'arrêt du reste de l'import).
  4. `.env` a changé → `Settings` (singleton chargé une fois au démarrage)
     ne peut pas être rechargé à chaud. L'endpoint termine par
     `os._exit(0)` après avoir répondu — `restart: unless-stopped` du
     compose relance `app` avec le nouvel `.env`. Le message de succès
     prévient : "application en cours de redémarrage, rechargez la page
     dans quelques secondes".

### Tests
- `tests/settings/test_export_import.py` — export produit le JSON attendu
  (secrets machine-locale absents) ; import réécrit `.env` correctement,
  réenregistre dossiers/partages (API + mount mockés comme dans
  `test_folders.py`/`test_shares.py`), n'écrit jamais dans `users`, rejette
  une version inconnue.

## Tests
- `tests/library/test_folders.py` — CRUD + appel API root-folder mocké
  (respx, comme `tests/arr/*`), cas succès et échec API.
- `tests/library/test_shares.py` — mount/umount mockés (`subprocess.run`
  patché), CRUD, remontage au démarrage, refus de suppression si référencé.
- `tests/ui/test_library_router.py` — endpoints HTTP, auth requise, rendu
  des fragments HTMX.

## Documentation à mettre à jour après implémentation
- `.ai/02-ARCHITECTURE.md` — nouveau composant "Gestion des dossiers de
  bibliothèque".
- `.ai/05-DEPLOYMENT.md` — nouvelles variables `.env`
  (`HOST_LIBRARY_ROOT`, `SHARES_MOUNT`), capacité `SYS_ADMIN` sur `app`.
- `install.sh` — prompt du dossier racine local (`HOST_LIBRARY_ROOT`,
  défaut `$HOME`) en plus du prompt USB existant.
- `docs/user/guide.md` — section "ajouter un dossier / un partage réseau" +
  section "exporter/importer la configuration".
