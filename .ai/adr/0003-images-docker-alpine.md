# ADR 0003 — Images Docker Alpine optimisées + nettoyage

**Statut** : accepté
**Date** : 2026-08-15

## Contexte
Le Pi 3 B+ a des ressources limitées (1 Go RAM, stockage souvent sur carte SD
ou disque USB modeste). Le temps de pull/build des images influence directement
la durée de l'installation one-liner (cf. `05-DEPLOYMENT.md`).

## Options considérées
1. **Images de base standard** (`python:3.11`, `debian`)
   - Avantages : compatibilité maximale, moins de surprises avec certaines libs
   - Inconvénients : images lourdes (300-900 Mo), plus longues à pull sur le Pi
2. **Images Alpine** (`python:3.11-alpine`)
   - Avantages : images très légères (souvent < 100 Mo), pull plus rapide,
     empreinte disque réduite — appréciable sur carte SD/USB limitée
   - Inconvénients : libc musl au lieu de glibc, certaines libs Python avec
     extensions C peuvent nécessiter une compilation plus longue ou poser
     des soucis de compatibilité (à tester au cas par cas)

## Décision
**Alpine pour l'image de l'appli maison** (le seul composant qu'on maîtrise
entièrement), avec build multi-stage et nettoyage systématique.

Pour les *arr et Jellyfin : garder leurs images officielles recommandées par
leurs mainteneurs plutôt que de forcer un ré-empaquetage Alpine non supporté
en amont — le risque de bugs subtils dépasse le gain de taille sur des
composants qu'on ne maintient pas.

## Bonnes pratiques retenues pour l'image de l'appli
- **Build multi-stage** : stage de build (compilation dépendances) séparé du
  stage final (runtime seul), pour ne pas embarquer les outils de build dans
  l'image finale
- **Nettoyage systématique** dans le même layer que l'installation :
  ```dockerfile
  RUN apk add --no-cache --virtual .build-deps gcc musl-dev \
      && pip install --no-cache-dir -r requirements.txt \
      && apk del .build-deps
  ```
- `--no-cache` sur apk, `--no-cache-dir` sur pip : pas de cache résiduel dans
  les layers
- Utilisateur non-root dans le conteneur final
- `.dockerignore` complet (tests, docs, `.git`) pour ne pas polluer le contexte
  de build

## Conséquences
- Image finale de l'appli visée < 150 Mo — mesurée à 99 Mo (build natif,
  vérification arm64 réelle non faite faute de `buildx` disponible en local,
  mais aucune dépendance Python de ce projet ne nécessite de compilation :
  toutes ont des wheels précompilées `musllinux` pour `aarch64`)
- Pipeline CI de build multi-arch (cf. `05-DEPLOYMENT.md`) doit valider la
  compatibilité Alpine/musl des dépendances Python utilisées avant chaque
  release, pas seulement au moment du choix initial

## Correctif (2026-08-18) — arm64 uniquement, pas armv7
`pydantic-settings` dépend de `pydantic-core` (extension Rust). PyPI ne
publie des wheels `musllinux` précompilées que pour `x86_64`/`aarch64`, pas
pour `armv7` — un Pi 3B+ en OS 32 bits forcerait donc une compilation Rust
dans le stage de build (toolchain Rust à installer, temps de build bien plus
long, va à l'encontre de "pas d'étape de build manuelle").

Décision : cibler **arm64 uniquement**. Le Cortex-A53 du Pi 3B+ est 64 bits
capable — impose Raspberry Pi OS 64 bits comme pré-requis (cf.
`01-CONTEXT.md`), en échange de zéro compilation native dans l'image finale.
Le support armv7 n'est pas exclu définitivement, mais nécessiterait de
rouvrir cette décision (toolchain Rust cross-compilée dans le stage builder)
si un besoin concret apparaît.
