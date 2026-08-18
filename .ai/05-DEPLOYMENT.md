# Déploiement

## Environnements
- **Dev** : machine de développement (x86), docker-compose avec *arr de test
- **Prod** : Raspberry Pi 3 B+ (ARM), OS 64 bits requis — image de l'appli
  buildée pour `arm64` uniquement, pas `armv7` (ADR 0003)

## Docker Compose (squelette)
Services : `app` (FastAPI), `jellyfin`, `sonarr`, `radarr`, `lidarr`, `readarr`,
`ntfy`, `calibre-web` (pont protocole Kobo Sync/OPDS, cf. ADR 0004), `caddy`
(reverse proxy). Volumes dédiés pour la bibliothèque (disque USB monté sur le
host) et pour la config de chaque service. Le volume `books-library` est
partagé en lecture-écriture par `app` (scan/enrichissement via `calibredb`) et
en lecture seule par `calibre-web` (indexation).

## Build multi-architecture
- `docker buildx build --platform linux/arm64` pour produire l'image depuis
  une machine x86 (évite de builder directement sur le Pi, lent)
- Image de l'appli maison en Alpine, multi-stage, nettoyée, utilisateur
  non-root, `HEALTHCHECK` sur `/health` (cf. ADR 0003) — vise < 150 Mo,
  mesurée à 99 Mo
- Images officielles conservées pour Jellyfin/*arr (pas de ré-empaquetage)

## Mise à jour
- Images taguées par version (semver), jamais `latest` en prod
- Procédure : `docker compose pull && docker compose up -d`, rollback = retag
  vers la version précédente

## Vérification pont Calibre-web
- Après `docker compose up -d`, vérifier que `/web` répond 404 via Caddy
  (`curl -I http://<host>:8000/web/` doit renvoyer 404, jamais l'UI Calibre-web)
- Vérifier `/opds/` répond (catalogue OPDS accessible)

## Sauvegarde
Config des *arr (bases SQLite internes) + config Jellyfin + base de l'appli →
sauvegarde régulière hors du Pi (autre disque ou cloud perso). La bibliothèque
média elle-même n'a pas besoin d'être sauvegardée si re-téléchargeable via
les *arr.

## Installation en une commande

Objectif : `curl -sSL <url>/install.sh | bash` doit suffire sur un Pi vierge
(Raspberry Pi OS fraîchement flashé).

Le script `install.sh` doit :
1. Vérifier/installer Docker + Docker Compose plugin
2. Récupérer `docker-compose.yml` + configs par défaut (repo ou release taguée,
   jamais `main` en prod pour éviter une install cassée par un commit en cours)
3. Générer un `.env` avec secrets aléatoires (mots de passe *arr, token webhook,
   `SESSION_SECRET`) — une valeur réelle générée à l'install, jamais laissée à
   `changeme` : l'appli refuse de démarrer si `SESSION_SECRET` vaut `changeme`
   ou est vide
4. Créer le compte `admin` (session cookie) avec mot de passe aléatoire, affiché une
   seule fois en fin d'install (cf. ADR 0002) — changement obligatoire à la
   première connexion
5. Détecter ou demander le point de montage du disque USB (seule interaction
   nécessaire — tout le reste doit avoir un défaut raisonnable)
6. Lancer `docker compose up -d` avec affichage de progression
   (le pull des ~6 images peut prendre 10-15 min sur Pi 3B+)
7. Afficher l'URL locale finale + rappel des identifiants générés

Détails d'implémentation :
- Les clés API *arr sont pré-semées dans le `config.xml` de chaque service
  (dans son volume Docker, avant premier démarrage) plutôt que copiées
  manuellement depuis chaque interface — zéro étape manuelle supplémentaire
- `install.sh --dry-run` affiche toutes les actions sans toucher à Docker
  ni au réseau — utile pour relire le script avant de l'exécuter pour de vrai
- `REF` (branche/tag ciblé par `install.sh`) vaut `main` tant qu'aucune
  release taguée n'existe — dette assumée, à corriger dès la première
  release (cf. `docs/superpowers/specs/2026-08-18-install-sh-design.md`)

Contraintes :
- Idempotent : relancer le script sur une install existante ne doit rien casser
  (détecter une install déjà présente, proposer mise à jour plutôt que ré-install)
- Écrire les logs d'install dans un fichier pour diagnostiquer un échec sans
  devoir tout relancer
- Un `uninstall.sh` symétrique est un bon complément, pas obligatoire en v1

## Répartition de charge (si Pi saturé)
- Déporter les *arr sur une seconde machine (NAS, mini-PC) ; le Pi garde
  uniquement `app` + `jellyfin` + `caddy`
- Aucun changement de code nécessaire, seulement les URLs dans la config
