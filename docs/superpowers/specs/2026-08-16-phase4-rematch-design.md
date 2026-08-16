# Phase 4 — Re-match manuel

**Date :** 2026-08-16
**Périmètre :** Action UI de re-match déclenchant un Manual Import côté *arr concerné, suivi d'un rafraîchissement des métadonnées Jellyfin

---

## Contexte

Phase 3 a livré l'UI de consultation (queue + bibliothèque) pour les 4 *arr. Phase 4 ajoute l'action de correction : depuis n'importe quel item de la bibliothèque, l'utilisateur peut déclencher un re-match manuel côté *arr, puis Jellyfin recalcule ses métadonnées sur l'item concerné.

**Critère de sortie :** Depuis l'UI, un item mal matché peut être corrigé : l'utilisateur choisit un candidat proposé par l'*arr, l'import est appliqué, et Jellyfin rafraîchit ses métadonnées sans intervention manuelle côté Jellyfin.

**Décisions actées (issues du brainstorming) :**
- Action générique disponible sur tout item suivi, pas conditionnée à un statut d'erreur détecté par l'app
- Manual Import = flux à 2 étapes : l'*arr propose des candidats, l'utilisateur choisit (pas d'auto-sélection)
- Le rafraîchissement Jellyfin est automatique après un import réussi, pas une action séparée
- Pas de mapping *arr → Jellyfin stocké en base : recherche live par titre au moment du re-match

---

## Structure des fichiers

| Fichier | Action | Rôle |
|---|---|---|
| `app/jellyfin/client.py` | Créer | Client API Jellyfin (recherche + refresh) |
| `app/rematch/rematch.py` | Créer | Logique métier : candidats + application |
| `app/ui/router.py` | Modifier | + routes GET/POST `/rematch/{arr}/{item_id}` |
| `app/ui/templates/_tab.html` | Modifier | + bouton "Re-match" par item |
| `app/ui/templates/_rematch.html` | Créer | Partial HTMX : liste des candidats + formulaire |
| `app/config.py` | Modifier | + `jellyfin_url`, `jellyfin_api_key` |
| `tests/jellyfin/test_client.py` | Créer | Tests client Jellyfin |
| `tests/rematch/test_rematch.py` | Créer | Tests logique métier |
| `tests/ui/test_router.py` | Modifier | + tests routes re-match |
| `.env.example` | Modifier | + 2 nouvelles variables |

---

## Client Jellyfin (`app/jellyfin/client.py`)

Même pattern que les clients *arr (`app/arr/*.py`) : httpx async, timeout 5s, erreur → log + `None`. Pas de cache — actions à la demande, pas de polling.

```python
async def search_items(query: str) -> list[dict] | None: ...
async def refresh_item(item_id: str) -> bool: ...
```

| Fonction | Endpoint | Détail |
|---|---|---|
| `search_items` | `GET /Items?searchTerm={query}&api_key={key}` | Retourne la liste brute Jellyfin (`Items`) |
| `refresh_item` | `POST /Items/{item_id}/Refresh?api_key={key}` | Body : `{"Replace All Metadata": true, "Replace All Images": false}` — force le recalcul sans écraser les fichiers locaux hors métadonnées |

---

## Logique métier (`app/rematch/rematch.py`)

```python
async def candidates(arr: str, item: dict) -> list[dict] | None: ...
async def apply(arr: str, item: dict, candidate: dict) -> bool: ...
```

### `candidates`
Appelle `GET /api/v3/manualimport?folder={item_path}` sur l'*arr concerné (endpoint commun aux 4 *arr, tous en `/api/v3`). Retourne la liste des candidats telle que renvoyée par l'*arr (y compris les `rejections` — mauvais type de média etc. sont déjà signalés par l'*arr, pas de logique de filtrage supplémentaire côté app).

- `item_path` : chemin du fichier/dossier tel qu'exposé par `item` (déjà présent dans les données queue/library de Phase 3)
- *arr injoignable → `None`, log erreur
- Aucun candidat → liste vide (pas une erreur)

### `apply`
1. `POST /api/v3/command` sur l'*arr avec `{"name": "ManualImport", "files": [candidate]}`
2. Si échec *arr → retourne `False` immédiatement, Jellyfin non sollicité
3. Si succès → `jellyfin.search_items(item["title"])`, prend le premier résultat, `jellyfin.refresh_item(id)`
4. Échec Jellyfin (introuvable ou injoignable) → loggé, n'affecte pas le retour (l'import *arr a déjà réussi) — l'UI affiche un avertissement secondaire, pas une erreur bloquante

---

## Configuration

```env
JELLYFIN_URL=http://jellyfin:8096
JELLYFIN_API_KEY=changeme
```

---

## UI (`app/ui/router.py`)

### Routes

```
GET  /rematch/{arr}/{item_id}   → partial candidats (appelle rematch.candidates)
POST /rematch/{arr}/{item_id}   → applique le candidat choisi (appelle rematch.apply), retourne partial résultat
```

`{arr}` validé contre `_CLIENTS` existant (404 sinon, comme `/tab/{arr}`).

### Templates

- `_tab.html` : bouton "Re-match" par ligne d'item, `hx-get="/rematch/{arr}/{id}" hx-target="#rematch-modal"`
- `_rematch.html` : liste des candidats retournés par `candidates()` avec bouton de sélection par candidat (`hx-post`) ; état vide → "Aucun candidat trouvé" ; état erreur *arr → "Service indisponible" ; après `apply()` → succès avec avertissement Jellyfin optionnel, ou échec explicite

---

## Tests

### `tests/jellyfin/test_client.py`
- `search_items` succès → liste retournée
- `search_items` erreur httpx → `None`, pas d'exception
- `refresh_item` succès → `True`
- `refresh_item` erreur httpx → `False`

### `tests/rematch/test_rematch.py`
- `candidates` succès → liste candidats
- `candidates` *arr injoignable → `None`
- `candidates` liste vide → `[]` (pas une erreur)
- `apply` *arr échoue → `False`, Jellyfin non appelé (mock non sollicité)
- `apply` *arr réussit + Jellyfin réussit → `True`
- `apply` *arr réussit + Jellyfin échoue → `True` (le succès *arr prime)

### `tests/ui/test_router.py` (ajouts)
- `GET /rematch/sonarr/1` → 200, liste candidats
- `GET /rematch/inconnu/1` → 404
- `POST /rematch/sonarr/1` avec candidat → 200, confirmation
- `POST /rematch/sonarr/1` *arr injoignable → 200, message d'erreur

---

## Hors périmètre

- Authentification → Phase 6
- Intégration lecture Jellyfin (lien direct/embed player) → Phase 5
- Mapping persistant *arr ↔ Jellyfin → non retenu, recherche live suffit pour ce périmètre
