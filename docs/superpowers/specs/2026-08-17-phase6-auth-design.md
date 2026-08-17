# Phase 6a — Authentification (session cookie) — Design

**Statut** : validé, en attente de plan d'implémentation
**Date** : 2026-08-17
**ADR associé** : `.ai/adr/0002-authentification-oauth.md`

## Contexte

ADR 0002 décide "OAuth" pour l'authentification mais renvoie le détail
technique ("bibliothèque OAuth précise, stockage des tokens") à une phase
ultérieure — jamais tranché depuis. Ce document précise ce détail pour une
appli mono-admin, locale, sans fournisseur d'identité tiers ni besoin
multi-tenant à ce stade.

## Décision : login par cookie de session, pas de flux OAuth littéral

"OAuth" dans l'ADR 0002 est réinterprété comme *authentification par
session serveur*, pas un flux OAuth2 littéral (pas de password grant, pas
de JWT). Justification :
- Pas de fournisseur d'identité tiers à intégrer, pas de multi-utilisateur
  prévu — la mécanique OAuth2 (tokens, refresh, expiration, clé de
  signature JWT) n'apporte rien pour un admin unique local
- Un cookie de session signé couvre déjà l'objectif de l'ADR : révocation
  possible (invalidation du cookie), compatible avec un accès distant futur
  derrière Caddy/TLS, sans le surcoût de code d'un flux OAuth2 complet
- Se rapprocher du YAGNI du reste du projet (cf. CLAUDE.md : pas
  d'abstraction pour un besoin hypothétique)

Si un jour plusieurs comptes distincts ou un accès tiers (ex. app mobile
dédiée) sont nécessaires, ce choix est reconsidéré à ce moment — pas
anticipé ici.

## Stockage de session : cookie signé, sans table serveur

`starlette.middleware.sessions.SessionMiddleware` (signature via
`itsdangerous`), cookie contenant `{"user_id": ...}`. Pas de table de
sessions en base : la déconnexion se fait en effaçant le cookie, pas de
révocation côté serveur nécessaire pour un admin unique local. Si un besoin
de révocation à distance apparaît plus tard (accès distant, appareil
perdu), ce choix sera revisité — pas un problème actuel.

## Hachage de mot de passe : `hashlib.scrypt` (stdlib), pas bcrypt

Contrainte de départ (cf. ADR 0003, CLAUDE.md — cible Pi 3B+/armv7, image
Alpine multi-stage sans étape de build manuelle) : `bcrypt` (ou
`passlib[bcrypt]`) est une extension native dont la couverture de wheels
précompilées pour armv7 est incertaine — un défaut de wheel forcerait une
compilation à l'installation, ce qui va à l'encontre de la contrainte
"pas de build manuel côté utilisateur" et alourdit l'image Docker (dette
de build tools dans une image censée rester nettoyée et légère).

`hashlib.scrypt` est dans la stdlib Python (depuis 3.6, nécessite OpenSSL
avec support scrypt — présent sur les builds Python standards), memory-hard
comme bcrypt, sans dépendance supplémentaire ni étape de compilation.
Vérification en temps constant via `hmac.compare_digest`.

Seule nouvelle dépendance ajoutée : `itsdangerous` (pure Python, requise
par `SessionMiddleware`).

## Schéma de données

Nouvelle table `users` dans le SQLite existant (`settings.db_path`, déjà
utilisé par `app/arr/cache.py` — pas de nouvelle base) :

```sql
CREATE TABLE IF NOT EXISTS users (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    username             TEXT UNIQUE NOT NULL,
    password_hash        TEXT NOT NULL,
    salt                 TEXT NOT NULL,
    must_change_password INTEGER NOT NULL DEFAULT 1
)
```

`salt` stocké séparément (requis par `hashlib.scrypt`, pas encodé dans le
hash comme le ferait bcrypt nativement).

## Amorçage du compte admin

`install.sh` n'existe pas encore (item Phase 6 séparé, plus tardif dans ce
plan). En attendant, l'amorçage se fait au démarrage de l'appli :

Dans le hook `lifespan` de `app/main.py` (à côté de l'appel existant à
`cache.init_db`) : si la table `users` est vide, générer un mot de passe
aléatoire (`secrets.token_urlsafe(16)`), le hacher, créer la ligne `admin`
avec `must_change_password=1`, logger le mot de passe en clair une seule
fois (`logger.warning`, visible via `docker compose logs`) — jamais écrit
dans `.env` ni en base en clair.

Quand `install.sh` sera écrit (item Phase 6 distinct), il lira cette ligne
de log au premier démarrage pour l'afficher à l'utilisateur — pas de
couplage de code entre les deux, juste une convention de log.

## Flux HTTP

- `GET /auth/login` — formulaire (username, password)
- `POST /auth/login` — vérifie via `hmac.compare_digest` sur le hash
  scrypt ; échec → ré-affiche le formulaire avec une erreur générique
  (pas de détail permettant l'énumération d'utilisateurs) ; succès → pose
  le cookie de session, redirige vers `/` (ou `/auth/change-password` si
  `must_change_password`)
- `GET /auth/change-password` / `POST /auth/change-password` — nécessite
  une session valide ; à la réussite, met `must_change_password=0`
- `POST /auth/logout` — efface le cookie de session

## Protection des routes

Dépendance FastAPI `require_login`, ajoutée à toutes les routes de
`app/ui/router.py` :
- Pas de session → redirection vers `/auth/login`
- Session valide mais `must_change_password=1` → redirection vers
  `/auth/change-password` (sauf sur cette route elle-même, pour éviter une
  boucle de redirection)

`/webhook/*` (Sonarr/Radarr/Lidarr/Readarr) reste **hors périmètre** de
cette protection : déjà authentifié par son propre header secret partagé,
appelé par les *arr eux-mêmes (pas de session interactive possible côté
appelant).

## Gestion des erreurs

Pas de limitation de tentatives ni de verrouillage de compte en v1 —
admin unique local, hors périmètre tant qu'un accès distant n'est pas en
jeu. À noter comme amélioration future si l'accès distant (mentionné dans
l'ADR) se concrétise.

## Tests

TDD, structure alignée sur les modules existants (`app/arr`,
`app/webhooks`) :
- `tests/auth/test_auth.py` — hachage/vérification de mot de passe,
  logique d'amorçage (table vide → admin créé avec mot de passe aléatoire
  loggé, `must_change_password=1`)
- `tests/auth/test_router.py` — flux HTTP login/logout/changement de mot
  de passe ; accès direct à une route protégée sans session → redirection
  (pas 200) ; mot de passe par défaut → redirection forcée vers
  `/auth/change-password` (exigence explicite de l'ADR 0002)
- `tests/ui/test_router.py` — les routes UI existantes nécessitent
  désormais une session : ajouter une fixture `authed_client` (ou
  équivalent auto-login) dans `tests/ui/conftest.py` plutôt que modifier
  chaque test un par un

## Fichiers touchés

- Créer : `app/auth/__init__.py`, `app/auth/auth.py`, `app/auth/router.py`
- Créer : `app/ui/templates/login.html`, `app/ui/templates/change_password.html`
- Modifier : `app/config.py` (+ `session_secret: str`)
- Modifier : `app/main.py` (SessionMiddleware, lifespan bootstrap, inclusion
  du router auth, dépendance `require_login` sur les routes UI)
- Modifier : `pyproject.toml` (+ `itsdangerous`)
- Modifier : `.env.example` (+ `SESSION_SECRET`)
- Créer : `tests/auth/__init__.py`, `tests/auth/test_auth.py`,
  `tests/auth/test_router.py`
- Modifier : `tests/conftest.py`, `tests/ui/conftest.py`

## Hors périmètre (v1)

- Multi-utilisateur (un seul compte `admin`)
- Révocation de session côté serveur / limitation de tentatives
- `install.sh` (item Phase 6 séparé, lira le mot de passe amorcé via les
  logs mais n'est pas construit dans ce lot)
- Remontée du statut OAuth littéral si un besoin tiers apparaît plus tard
  (cf. section Décision)
