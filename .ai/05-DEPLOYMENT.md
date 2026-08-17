# Déploiement

## Environnements
- **Dev** : machine de développement (x86), docker-compose avec *arr de test
- **Prod** : Raspberry Pi 3 B+ (ARM), images buildées pour `arm/v7` ou `arm64`

## Docker Compose (squelette)
Services : `app` (FastAPI), `jellyfin`, `sonarr`, `radarr`, `lidarr`, `readarr`,
`ntfy`, `calibre-web` (pont protocole Kobo Sync/OPDS, cf. ADR 0004), `caddy`
(reverse proxy). Volumes dédiés pour la bibliothèque (disque USB monté sur le
host) et pour la config de chaque service. Le volume `books-library` est
partagé en lecture-écriture par `app` (scan/enrichissement via `calibredb`) et
en lecture seule par `calibre-web` (indexation).

## Build multi-architecture
- `docker buildx` pour produire des images compatibles ARM depuis une machine x86
  (évite de builder directement sur le Pi, lent)
- Image de l'appli maison en Alpine, multi-stage, nettoyée (cf. ADR 0003) —
  vise < 150 Mo pour accélérer le pull sur Pi
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
3. Générer un `.env` avec secrets aléatoires (mots de passe *arr, token webhook)
4. Créer le compte `admin` OAuth avec mot de passe aléatoire, affiché une
   seule fois en fin d'install (cf. ADR 0002) — changement obligatoire à la
   première connexion
5. Détecter ou demander le point de montage du disque USB (seule interaction
   nécessaire — tout le reste doit avoir un défaut raisonnable)
6. Lancer `docker compose up -d` avec affichage de progression
   (le pull des ~6 images peut prendre 10-15 min sur Pi 3B+)
7. Afficher l'URL locale finale + rappel des identifiants générés

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
