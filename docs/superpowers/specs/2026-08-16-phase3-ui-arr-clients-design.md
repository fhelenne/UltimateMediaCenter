# Phase 3 — UI unifiée + clients *arr

**Date :** 2026-08-16  
**Périmètre :** Clients API lecture seule pour chaque *arr + cache SQLite TTL + UI à tabs avec pagination

---

## Contexte

Phase 2 a livré les webhooks pour les 4 *arr → ntfy. Phase 3 ajoute une interface web unifiée permettant de consulter la queue active et la bibliothèque de chaque *arr, avec un cache SQLite TTL pour ne pas saturer les API sur Raspberry Pi 3 B+.

**Critère de sortie :** Ouvrir l'UI affiche la queue et la bibliothèque de chaque *arr, paginées, avec gestion gracieuse des services injoignables.

---

## Structure des fichiers

| Fichier | Action | Rôle |
|---|---|---|
| `app/arr/cache.py` | Créer | SQLite TTL cache (get/set) |
| `app/arr/sonarr.py` | Créer | Client API Sonarr (queue + library) |
| `app/arr/radarr.py` | Créer | Client API Radarr |
| `app/arr/lidarr.py` | Créer | Client API Lidarr |
| `app/arr/readarr.py` | Créer | Client API Readarr |
| `app/ui/router.py` | Créer | Routes GET / et GET /tab/{arr} |
| `app/ui/templates/base.html` | Créer | Layout HTML, HTMX CDN |
| `app/ui/templates/index.html` | Créer | Page tabs |
| `app/ui/templates/_tab.html` | Créer | Partial HTMX : queue + bibliothèque paginées |
| `app/config.py` | Modifier | + 4×{arr}_url, 4×{arr}_api_key, cache_ttl |
| `app/main.py` | Modifier | Montage du router UI + init DB |
| `tests/arr/test_cache.py` | Créer | Tests unitaires cache |
| `tests/arr/test_sonarr.py` | Créer | Tests client Sonarr |
| `tests/arr/test_radarr.py` | Créer | Tests client Radarr |
| `tests/arr/test_lidarr.py` | Créer | Tests client Lidarr |
| `tests/arr/test_readarr.py` | Créer | Tests client Readarr |
| `tests/ui/test_router.py` | Créer | Tests routes UI |
| `.env.example` | Modifier | + 9 nouvelles variables |

---

## Cache SQLite TTL (`app/arr/cache.py`)

### Schéma

```sql
CREATE TABLE IF NOT EXISTS arr_cache (
    key        TEXT PRIMARY KEY,
    data       TEXT NOT NULL,
    expires_at REAL NOT NULL
);
```

### Interface

```python
def init_db(db_path: str) -> None: ...
def get(db_path: str, key: str) -> dict | list | None: ...
def set(db_path: str, key: str, data: dict | list, ttl: int) -> None: ...
```

- `get` retourne `None` si absent ou expiré
- `set` fait un UPSERT (`INSERT OR REPLACE`)
- `db_path` injecté (pas de singleton global) — facilite les tests avec `":memory:"`

---

## Clients *arr

### Pattern commun

Chaque client expose :
```python
async def queue(page: int = 1, page_size: int = 25) -> list[dict]
async def library(page: int = 1, page_size: int = 25) -> list[dict]
```

Logique interne :
1. Clé cache : `f"{arr}:queue:p{page}"` / `f"{arr}:library:p{page}"`
2. `cache.get(...)` → si résultat : retourner directement
3. Sinon : appel httpx avec header `X-Api-Key`, timeout 5s
4. Stockage en cache avec `settings.cache_ttl`
5. Erreur httpx → log + retourne `[]`

### Endpoints *arr

| *arr | Queue | Library |
|---|---|---|
| Sonarr | `GET /api/v3/queue` | `GET /api/v3/series` |
| Radarr | `GET /api/v3/queue` | `GET /api/v3/movie` |
| Lidarr | `GET /api/v3/queue` | `GET /api/v3/artist` |
| Readarr | `GET /api/v3/queue` | `GET /api/v3/book` |

Paramètres de pagination passés à l'API *arr : `?page={page}&pageSize={page_size}` (Sonarr/Radarr/Readarr supportent ces params natifs ; Lidarr idem).

---

## Configuration

Nouvelles variables dans `app/config.py` / `.env` :

```env
SONARR_URL=http://sonarr:8989
SONARR_API_KEY=changeme
RADARR_URL=http://radarr:7878
RADARR_API_KEY=changeme
LIDARR_URL=http://lidarr:8686
LIDARR_API_KEY=changeme
READARR_URL=http://readarr:8787
READARR_API_KEY=changeme
CACHE_TTL=30
DB_PATH=data/cache.db
```

`data/cache.db` monté comme volume Docker pour persistance entre redémarrages.

---

## UI (`app/ui/`)

### Routes

```
GET /                          → page tabs (onglet Sonarr actif par défaut)
GET /tab/{arr}?page=1          → partial HTMX (queue + bibliothèque paginées)
```

`{arr}` ∈ `sonarr | radarr | lidarr | readarr`

### Templates

**`base.html`** : layout HTML5, HTMX via CDN (`https://unpkg.com/htmx.org`), Pico CSS via CDN (< 10 Ko, pas de build). Pas de JS custom.

**`index.html`** : 4 tabs fixes. Onglet actif déclenche `hx-get="/tab/sonarr" hx-trigger="load" hx-target="#tab-content"`. Changement d'onglet = `hx-get="/tab/{arr}" hx-target="#tab-content"`.

**`_tab.html`** (partial) :
- Section **Queue active** : titre + statut par item
- Section **Bibliothèque** : titre + statut (`monitored` / `missing` / `downloaded`)
- Pagination : liens Précédent / Suivant via `hx-get="/tab/{arr}?page=N"`
- Si liste vide ET erreur *arr : message "Service indisponible"
- Si liste vide sans erreur : "Aucun élément"

### Gestion d'erreur

Si *arr injoignable → client retourne `[]` + log. L'onglet affiche "Service indisponible". Les autres onglets restent fonctionnels (appels indépendants).

---

## Tests

### `tests/arr/test_cache.py`
- `get` sur clé absente → `None`
- `get` sur clé expirée → `None`
- `get` sur clé valide → données
- `set` puis `get` → round-trip
- `set` upsert (écraser une clé existante)

Tous les tests utilisent `db_path=":memory:"`.

### `tests/arr/test_{arr}.py` (× 4)
- Cache hit → httpx non appelé
- Cache miss → httpx appelé, réponse stockée
- httpx timeout → retourne `[]`, pas d'exception
- Pagination : page 2 utilise clé cache différente

### `tests/ui/test_router.py`
- `GET /` → 200, contient les 4 tabs
- `GET /tab/sonarr` → 200 (cache mocké avec données)
- `GET /tab/sonarr?page=2` → 200
- *arr injoignable → 200, contient "Service indisponible"

---

## Hors périmètre

- Actions (re-match, Manual Import) → Phase 4
- Authentification → Phase 6
- Jellyfin → Phase 5
- Déduplication webhooks → Phase 3 du plan initial, reportée après l'UI
