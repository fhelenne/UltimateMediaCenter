# CLAUDE.md

Instructions pour Claude Code sur ce dépôt. Toute la documentation projet vit
dans `.ai/`. Ne charge que les fichiers pertinents pour la tâche en cours —
ne pas tout lire par défaut. Ne pas précharger tout `.ai/` en début de
session « au cas où » : utiliser le tableau de routage ci-dessous à la
demande, tâche par tâche.

## Toujours lire en premier
- `.ai/01-CONTEXT.md` — vision, contraintes, périmètre. Base minimale avant
  toute tâche non triviale.

## Routage par type de tâche

| Tâche | Fichiers à lire |
|---|---|
| Comprendre le système, ajouter/modifier un composant | `.ai/02-ARCHITECTURE.md`, `.ai/architecture-media-center.mermaid` |
| Écrire ou modifier du code | `.ai/03-QUALITY.md` (conventions), puis le fichier ARCHITECTURE si le composant touché n'est pas déjà clair |
| Écrire ou modifier des tests | `.ai/04-TESTING.md` |
| Docker, docker-compose, script d'installation, CI/CD | `.ai/05-DEPLOYMENT.md` |
| Savoir où en est le projet / prochaine étape | `.ai/DEVELOPMENT_PLAN.md` |
| Comprendre pourquoi un choix technique a été fait | `.ai/adr/` — chercher l'ADR dont le titre correspond au sujet (ex. auth → `0002-authentification-oauth.md`) avant de proposer une alternative |
| Prendre une nouvelle décision structurante | lire `.ai/adr/0000-template.md`, créer un nouvel ADR numéroté, puis mettre à jour les fichiers impactés (voir section Propagation) |

## Index des ADR existants
- `0001-interface-ssr-htmx.md` — SSR + HTMX plutôt que SPA
- `0002-authentification-oauth.md` — OAuth + compte admin par défaut
- `0003-images-docker-alpine.md` — images Docker Alpine + nettoyage
- `0004-sync-kobo-calibreweb.md` — Calibre-web en pont protocole Kobo Sync/OPDS

## Règle de propagation
Ce projet documente les décisions en ADR puis les répercute dans les fichiers
concernés (CONTEXT, ARCHITECTURE, DEVELOPMENT_PLAN, DEPLOYMENT, schéma
mermaid). Après avoir créé ou modifié un ADR, toujours vérifier et mettre à
jour les fichiers listés dans sa section "Conséquences" — ne jamais laisser
un ADR non reflété ailleurs dans la doc.

## Contraintes non négociables à garder en tête sur toute tâche
- Cible matérielle : Raspberry Pi 3 B+ (1 Go RAM) — éviter tout ajout gourmand
  sans le justifier explicitement
- Installation doit rester one-liner (`install.sh`), idempotente, sans étape
  de build manuelle côté utilisateur
- Ne jamais réimplémenter une fonctionnalité déjà déléguée à un outil tiers
  (*arr, Jellyfin, Calibre-web) sauf justification explicite en ADR
