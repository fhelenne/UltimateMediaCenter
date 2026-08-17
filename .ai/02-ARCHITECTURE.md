# Architecture

Voir le schéma système : `architecture-media-center.mermaid`

## Stack retenue
- **Backend** : Python 3.11+ / FastAPI (léger, async, bonne doc, adapté au Pi)
- **Frontend** : SSR (FastAPI + Jinja2) + HTMX pour l'interactivité ciblée —
  décision actée en ADR 0001, pas de build JS dans le pipeline d'installation
- **Base de données** : SQLite (suffisant pour un usage mono-foyer, zéro admin)
- **Reverse proxy** : Caddy ou Nginx (TLS local, routage vers Jellyfin/appli)
- **Conteneurisation** : Docker Compose (isolation, portabilité, montée de version simple)

## Composants internes

### 1. Orchestrateur
Interroge les API des *arr (statuts, bibliothèques, recherche), cache les
réponses (TTL court) pour ne pas spammer les *arr depuis l'UI.

### 2. Récepteur de webhooks
Endpoints `/webhook/{sonarr,radarr,lidarr,readarr}` — valide la source
(secret partagé), parse l'event, transmet au module notifications.
Idempotent : un même event rejoué ne duplique pas une notif.

### 3. Module notifications
Formatte le message (média, action, lien direct), envoie vers
ntfy/Gotify/Telegram (adaptateur interchangeable).

### 4. Module re-match
Déclenche un Manual Import côté *arr concerné, bascule les paramètres
metadata Jellyfin (ignorer fichiers locaux) via son API.

### 5. Authentification
Session cookie signée (via `itsdangerous`, Starlette `SessionMiddleware`) sur
un compte admin unique, table `users` dans le même fichier SQLite que le
cache de l'orchestrateur. Protège toutes les routes UI ; les webhooks en sont
exclus (authentification propre par secret partagé, cf. ADR 0002).

## Flux de données principaux
1. Dépôt fichier → *arr scanne → matche → notifie ton appli (webhook) → notif push
2. Utilisateur ouvre l'UI → orchestrateur interroge les *arr → affichage unifié
3. Erreur de matching → UI déclenche re-match → *arr/Jellyfin recalculent

## Décisions différées (à trancher en ADR)
- Déploiement mono-Pi vs *arr déportés sur autre machine
