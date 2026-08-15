# Phase 1 — Webhook Sonarr → ntfy

**Date :** 2026-08-15  
**Périmètre :** MVP notifications — endpoint Sonarr, envoi ntfy, docker-compose

---

## Contexte

Première brique fonctionnelle du media center : recevoir un webhook Sonarr quand un épisode est téléchargé, envoyer une notification push via ntfy auto-hébergé.

Critère de sortie : une sortie d'épisode dans Sonarr déclenche une vraie notif sur le téléphone.

---

## Structure du projet

```
ultimatemediacenter/
├── app/
│   ├── main.py                  # FastAPI app, montage des routers
│   ├── config.py                # pydantic-settings
│   ├── webhooks/
│   │   ├── __init__.py
│   │   └── sonarr.py            # router + modèles Pydantic + parsing
│   └── notifications/
│       ├── __init__.py
│       └── ntfy.py              # client httpx async
├── tests/
│   ├── webhooks/
│   │   └── test_sonarr.py
│   └── notifications/
│       └── test_ntfy.py
├── docker-compose.yml
├── Dockerfile
├── .env.example
└── pyproject.toml
```

---

## Configuration

Variables d'environnement (`.env`, non versionné ; `.env.example` versionné) :

```
NTFY_URL=http://ntfy:80
NTFY_TOPIC=mediacenter
SONARR_SECRET=changeme
```

Chargées via `pydantic-settings`.

---

## Events Sonarr supportés

| eventType  | Comportement                          |
|------------|---------------------------------------|
| `Download` | Parse payload, envoie notif ntfy      |
| `Test`     | Retourne 200 `{"status": "ok"}`, pas de notif |

---

## Flux de données

```
Sonarr POST /webhook/sonarr
  → Header X-Sonarr-Secret validé (403 si absent/incorrect)
  → Body parsé en SonarrEvent (Pydantic)
  → eventType == "Test"     → 200 {"status": "ok"}
  → eventType == "Download" → ntfy.send(titre, corps) → 200
  → Payload malformé        → 422 (FastAPI natif)
  → ntfy injoignable        → log erreur, retourne 200 quand même
```

Sonarr reçoit toujours 200 sauf auth invalide — évite les retries intempestifs.

---

## Modèles Pydantic (`webhooks/sonarr.py`)

```python
class SonarrEpisode(BaseModel):
    title: str
    seasonNumber: int
    episodeNumber: int

class SonarrSeries(BaseModel):
    title: str

class SonarrQuality(BaseModel):
    quality: dict  # {"name": "HDTV-1080p", ...}

class SonarrEvent(BaseModel):
    eventType: Literal["Download", "Test"]
    series: SonarrSeries | None = None
    episodes: list[SonarrEpisode] | None = None
    quality: SonarrQuality | None = None
```

Champs `series`/`episodes`/`quality` optionnels — absents sur l'event `Test`.

---

## Format de la notification ntfy

| Champ  | Valeur                                      |
|--------|---------------------------------------------|
| Titre  | `{series.title} S{season:02d}E{ep:02d}`     |
| Corps  | `{episode.title} · {quality.quality["name"]}` |

---

## Client ntfy (`notifications/ntfy.py`)

- `POST {NTFY_URL}/{NTFY_TOPIC}`
- Headers : `Title`, `Content-Type: text/plain`
- Timeout explicite : 5 s
- `httpx.HTTPError` loguée (JSON structuré), pas reraisée

---

## Tests

### Unitaires / intégration (`httpx.AsyncClient` + `respx`)

**`test_sonarr.py`**
- Payload `Download` valide → 200, ntfy appelé avec bon titre/corps
- Payload `Test` → 200, ntfy non appelé
- Secret absent → 403
- Secret incorrect → 403
- Payload malformé → 422, pas de crash

**`test_ntfy.py`**
- Envoi correct → requête ntfy vérifiée (titre, corps, topic)
- ntfy timeout → pas d'exception levée vers l'appelant

**Couverture cible :** 80 % sur `app/webhooks/` et `app/notifications/`.

---

## Docker Compose

```yaml
services:
  app:
    build: .
    env_file: .env
    ports: ["8000:8000"]
    depends_on: [ntfy]

  ntfy:
    image: binwiederhier/ntfy:latest
    command: serve
    ports: ["80:80"]
    volumes: ["ntfy-data:/var/cache/ntfy"]

volumes:
  ntfy-data:
```

Image app : Alpine multi-stage (ADR 0003), cible `< 150 Mo`.

---

## Ce qui est hors périmètre (Phase 1)

- Radarr / Lidarr / Readarr (Phase 2)
- Déduplication des events rejoués (Phase 2)
- UI (Phase 3)
- Auth OAuth (Phase 6)
