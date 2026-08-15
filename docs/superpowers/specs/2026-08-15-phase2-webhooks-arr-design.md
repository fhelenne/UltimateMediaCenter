# Phase 2 — Webhooks Radarr / Lidarr / Readarr

**Date :** 2026-08-15  
**Périmètre :** Extension du système de webhooks aux trois autres *arr + extraction d'un handler partagé

---

## Contexte

Phase 1 a livré le webhook Sonarr → ntfy. Phase 2 étend le même pattern à Radarr, Lidarr et Readarr, en extrayant la logique commune dans `app/webhooks/base.py` pour éviter la duplication.

Déduplication des events reportée à Phase 3 (avec la DB). Adaptateur de notif interchangeable hors périmètre (ntfy suffit).

**Critère de sortie :** Un téléchargement dans chacun des trois *arr déclenche une notification push formatée sur le téléphone.

---

## Structure des fichiers

| Fichier | Action | Rôle |
|---|---|---|
| `app/webhooks/base.py` | Créer | `handle_webhook()` — logique commune |
| `app/webhooks/sonarr.py` | Modifier | Refactorisé pour appeler `base.handle_webhook` |
| `app/webhooks/radarr.py` | Créer | Modèles + `_format()` + router |
| `app/webhooks/lidarr.py` | Créer | Modèles + `_format()` + router |
| `app/webhooks/readarr.py` | Créer | Modèles + `_format()` + router |
| `app/config.py` | Modifier | + `RADARR_SECRET`, `LIDARR_SECRET`, `READARR_SECRET` |
| `app/main.py` | Modifier | Montage des 3 nouveaux routers |
| `tests/webhooks/test_base.py` | Créer | Tests logique commune |
| `tests/webhooks/test_radarr.py` | Créer | Tests Radarr |
| `tests/webhooks/test_lidarr.py` | Créer | Tests Lidarr |
| `tests/webhooks/test_readarr.py` | Créer | Tests Readarr |
| `.env.example` | Modifier | + 3 nouvelles variables |
| `docker-compose.yml` | Modifier | + services radarr, lidarr, readarr |

---

## Handler partagé (`app/webhooks/base.py`)

```python
async def handle_webhook(
    event: BaseModel,
    received_secret: str | None,
    expected_secret: str,
    on_download: Callable[[BaseModel], tuple[str, str]],
) -> dict[str, str]
```

**Logique :**
1. `received_secret != expected_secret` → `HTTP 403`
2. `event.eventType == "Test"` → `{"status": "ok"}` (sans appel ntfy)
3. `event.eventType == "Download"` → `title, body = on_download(event)` → `ntfy.send(title, body)` → `{"status": "ok"}`
4. ntfy injoignable → log erreur, retourne `200` quand même (logique dans `ntfy.send`)

---

## Endpoints et configuration

| Service | Endpoint | Header secret |
|---|---|---|
| Radarr | `POST /webhook/radarr` | `X-Radarr-Secret` |
| Lidarr | `POST /webhook/lidarr` | `X-Lidarr-Secret` |
| Readarr | `POST /webhook/readarr` | `X-Readarr-Secret` |

---

## Modèles Pydantic

### Radarr

```python
class RadarrMovie(BaseModel):
    title: str
    year: int

class RadarrMovieFile(BaseModel):
    quality: str

class RadarrEvent(BaseModel):
    eventType: Literal["Download", "Test"]
    movie: RadarrMovie | None = None
    movieFile: RadarrMovieFile | None = None
```

### Lidarr

```python
class LidarrArtist(BaseModel):
    name: str

class LidarrAlbum(BaseModel):
    title: str

class LidarrTrackFile(BaseModel):
    quality: str

class LidarrEvent(BaseModel):
    eventType: Literal["Download", "Test"]
    artist: LidarrArtist | None = None
    albums: list[LidarrAlbum] | None = None
    trackFiles: list[LidarrTrackFile] | None = None
```

### Readarr

```python
class ReadarrAuthor(BaseModel):
    name: str

class ReadarrBook(BaseModel):
    title: str

class ReadarrBookFile(BaseModel):
    quality: str

class ReadarrEvent(BaseModel):
    eventType: Literal["Download", "Test"]
    author: ReadarrAuthor | None = None
    books: list[ReadarrBook] | None = None
    bookFiles: list[ReadarrBookFile] | None = None
```

---

## Format des notifications

| Service | Titre | Corps |
|---|---|---|
| Radarr | `{movie.title} ({movie.year})` | `{movieFile.quality}` |
| Lidarr | `{artist.name} — {albums[0].title}` | `{trackFiles[0].quality}` |
| Readarr | `{books[0].title} — {author.name}` | `{bookFiles[0].quality}` |

Valeur de repli `"Unknown"` si champ absent.

---

## Configuration

Nouvelles variables dans `.env` / `app/config.py` :

```env
RADARR_SECRET=changeme
LIDARR_SECRET=changeme
READARR_SECRET=changeme
```

---

## Tests

### `tests/webhooks/test_base.py`
- Secret absent → 403
- Secret incorrect → 403
- `Test` event → 200, ntfy non appelé
- `Download` → ntfy appelé avec bon titre/corps
- ntfy timeout → 200 quand même

> Testé via Radarr (le plus simple) — la logique `base.py` est identique pour tous.

### `tests/webhooks/test_radarr.py`
- Payload `Download` valide → 200, ntfy avec `"The Dark Knight (2008)"` / `"Bluray-1080p"`
- Payload `Test` → 200
- Payload malformé → 422

### `tests/webhooks/test_lidarr.py`
- Payload `Download` valide → 200, ntfy avec `"Radiohead — OK Computer"` / `"FLAC"`
- Premier album utilisé si `albums` contient plusieurs entrées
- Payload `Test` → 200
- Payload malformé → 422

### `tests/webhooks/test_readarr.py`
- Payload `Download` valide → 200, ntfy avec `"Dune — Frank Herbert"` / `"EPUB"`
- Payload `Test` → 200
- Payload malformé → 422

### Non-régression
`tests/webhooks/test_sonarr.py` **doit rester vert** après le refactor de `sonarr.py`.

---

## Refactor Sonarr

`sonarr.py` perd son bloc de logique inline (secret check + dispatch) et appelle `base.handle_webhook`. Les modèles Pydantic et la fonction `_format()` restent dans `sonarr.py`. Aucun changement de comportement observable — les tests existants le confirment.

---

## Docker Compose

Ajout des services `radarr`, `lidarr`, `readarr` sur les ports `7878`, `8686`, `8787`. Chacun configuré pour envoyer vers `http://app:8000/webhook/{arr}` avec le header secret correspondant (configuration via l'API de chaque service, comme fait pour Sonarr).

---

## Hors périmètre

- Déduplication des events rejoués (Phase 3)
- Adaptateur de notif interchangeable (Phase future)
- UI (Phase 3)
