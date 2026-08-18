# install.sh — installation one-liner — Design

**Statut** : validé, en attente de plan d'implémentation
**Date** : 2026-08-18
**Réfs** : `.ai/DEVELOPMENT_PLAN.md` Phase 6, `.ai/05-DEPLOYMENT.md` section
"Installation en une commande", ADR 0002 (auth), ADR 0003 (image Docker)

## Contexte

Dernier gros morceau de Phase 6 avant la doc utilisateur finale. Objectif :
`curl -sSL <url>/install.sh | bash` doit suffire sur un Raspberry Pi OS 64
bits fraîchement flashé pour obtenir un système fonctionnel — app, *arr,
Jellyfin, Calibre-web, Caddy, ntfy — sans étape de build manuelle et avec une
seule interaction utilisateur (le point de montage du disque USB).

Deux prérequis découverts pendant l'exploration, traités dans ce lot :
- `docker-compose.yml` ne définit **aucun service `jellyfin`**, alors que
  `.env.example`, le client `app/jellyfin/client.py` et `05-DEPLOYMENT.md`
  le supposent tous présent. Sans le corriger, `install.sh` livrerait un
  système où le lien Jellyfin de l'UI et `JELLYFIN_URL` pointent dans le vide.
- Aucun tag git n'existe encore sur ce dépôt, alors que la contrainte
  documentée est "jamais `main` en prod". Traité comme une dette assumée
  (voir section Décisions).

## Décisions

### `docker-compose.yml` : ajout du service `jellyfin`

Image `linuxserver/jellyfin`, même pattern PUID/PGID/TZ que les autres
services *arr, port `8096`, volumes dédiés pour la config et pour la
bibliothèque média (accès en lecture aux mêmes volumes que les *arr
organisent — `sonarr-tv`, `radarr-movies`, `lidarr-music`, `books-library`,
en lecture seule côté Jellyfin puisqu'il ne fait qu'indexer/streamer).

### Pas de tag git existant — `REF=main` assumé, documenté comme dette

La contrainte "jamais `main` en prod" ne peut pas être honorée tant qu'aucune
release taguée n'existe. Décision : `install.sh` référence la branche/tag
cible via **une seule variable en tête de script** (`REF="main"`), avec un
avertissement explicite affiché à l'exécution tant que `REF` vaut `main`
("aucune release taguée disponible — mettre à jour install.sh à la première
release"). Corriger la contrainte elle-même (mettre en place un vrai
pipeline de release taguée) est explicitement **hors périmètre** de ce lot —
ce serait sur-ingénierie avant d'avoir un historique de releases à gérer.

### Clés API *arr : pré-remplissage de `config.xml`, pas de copier-coller manuel

Sonarr/Radarr/Lidarr/Readarr génèrent chacun leur propre clé API au premier
démarrage, stockée dans leur `config.xml` interne. Pour respecter la
contrainte "une seule interaction utilisateur", `install.sh` génère une clé
aléatoire par *arr et l'écrit dans un `config.xml` minimal placé dans le
volume de config de chaque service **avant** son premier démarrage (via un
conteneur `alpine` jetable montant le volume nommé), puis écrit la même
valeur dans `.env`. Chaque *arr démarre donc déjà configuré avec la clé
que l'appli utilisera.

Contenu minimal du `config.xml` pré-semé (par service, `Port` variant selon
le service — 8989/7878/8686/8787) :
```xml
<Config>
  <LogLevel>info</LogLevel>
  <Port>8989</Port>
  <ApiKey>GENERATED_KEY</ApiKey>
</Config>
```
Chaque *arr complète les champs manquants avec ses propres valeurs par
défaut au premier démarrage — ne remplacer que ce qui doit être connu à
l'avance (port, clé API).

### Idempotence : présence de `.env` dans le répertoire cible

Si `.env` existe déjà dans le répertoire d'installation, `install.sh` traite
l'exécution comme une **mise à jour** : ne régénère ni secrets ni clés API,
ne re-sème aucun `config.xml`, se contente de `docker compose pull &&
docker compose up -d`. Sinon, traité comme une installation fraîche
(génération complète).

### Vérification sans matériel Pi réel

Pas d'accès à un Raspberry Pi physique dans cet environnement. Vérification
possible :
- `shellcheck` via `docker run --rm -v "$PWD:/mnt" koalaman/shellcheck:stable install.sh`
  (shellcheck n'est pas installé localement, mais Docker l'est)
- `docker compose config -q` sur le `docker-compose.yml` mis à jour, valide
  la syntaxe et les références de service
- Un mode `--dry-run` intégré au script : affiche chaque action sans toucher
  à Docker ni au réseau — sert à la fois d'outil de revue et de test
  fonctionnel local
- Exécution réelle (hors `--dry-run`) de la génération de secrets et du
  pré-semage de `config.xml` contre un répertoire de test local — ces
  étapes ne dépendent pas du matériel Pi, seulement de Docker, disponible ici
- Ce que cette vérification **ne couvre pas** : le comportement réel sur
  Raspberry Pi OS 64 bits vierge (installation de Docker via
  `get.docker.com`, détection du point de montage USB en conditions
  réelles, temps de pull des ~6 images sur un Pi 3B+). Ces points restent à
  valider par un test manuel sur matériel réel avant la release taguée qui
  fixera `REF`.

### `uninstall.sh` : non traité dans ce lot

Le plan de déploiement le liste comme "bon complément, pas obligatoire en
v1" — YAGNI, pas construit ici.

### Modèle réseau/auth des *arr : non retouché

Les ports des *arr restent exposés directement sur l'hôte comme
actuellement configuré dans `docker-compose.yml` (pré-existant, hors
périmètre de ce lot — `install.sh` ne doit pas redessiner silencieusement ce
choix).

## Flux d'exécution (`install.sh`)

1. `check_prereqs` — vérifie Docker + plugin Compose ; installe via le
   script officiel `get.docker.com` si absent
2. `is_existing_install` — teste la présence de `.env` dans le répertoire
   cible
3. `fetch_release` — `git clone --branch "$REF" --depth 1 <repo>` (avec
   avertissement si `REF=main`)
4. Si installation fraîche :
   - `generate_env` — secrets aléatoires (`SESSION_SECRET`, `*_SECRET`
     webhook, `*_API_KEY` par *arr) via `openssl rand -base64 32` (ou
     `/dev/urandom` si `openssl` absent), écrit `.env` à partir de
     `.env.example` ; seule interaction : détection ou demande du point de
     montage USB (auto-détection `/media/*`/`/mnt/*`, sinon prompt)
   - `seed_arr_configs` — pré-sème `config.xml` par *arr (voir section
     Décisions)
5. `up` — `docker compose pull && docker compose up -d`, progression
   affichée
6. `summary` — affiche l'URL locale finale, récupère le mot de passe admin
   initial depuis `docker compose logs app` (déjà loggé une fois au
   bootstrap de l'appli, cf. Phase 6a), rappelle le lien vers
   `docs/user/liseuse-kobo.md` pour la config liseuse
7. Tout au long : sortie dupliquée vers un fichier de log d'install
   (`install.log` dans le répertoire cible), pour diagnostiquer un échec
   sans tout relancer

`--dry-run` : exécute le même flux mais n'invoque aucune commande Docker/git
réelle, affiche uniquement ce qui serait fait.

## Gestion des erreurs

- Toute étape qui échoue arrête le script (`set -euo pipefail`), le message
  d'erreur et le contenu du fichier de log restent consultables
- Ré-exécution après échec sur une installation fraîche non aboutie : si
  `.env` n'a pas encore été écrit au moment de l'échec, la ré-exécution est
  traitée comme une nouvelle tentative d'installation fraîche (pas de
  fichiers partiels dangereux — `.env` n'est écrit qu'une fois toutes les
  valeurs générées avec succès)

## Fichiers touchés

- Créer : `install.sh`
- Modifier : `docker-compose.yml` (service `jellyfin`)
- Modifier : `.ai/05-DEPLOYMENT.md` (préciser le pré-semage `config.xml`,
  la contrainte `REF=main` assumée comme dette, le mode `--dry-run`)
- Modifier : `.ai/DEVELOPMENT_PLAN.md` (cocher l'item `install.sh` une fois
  fait)

## Hors périmètre

- Pipeline de release taguée (dette assumée, voir Décisions)
- `uninstall.sh`
- Redesign du modèle réseau/auth des *arr
- Test réel sur matériel Raspberry Pi physique (à faire manuellement avant
  la première release taguée)
