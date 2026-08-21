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

## Variables d'environnement

- `USB_MOUNT` : chemin du point de montage du disque USB externe sur l'hôte —
  utilisé uniquement par docker-compose.yml (driver_opts bind mount des volumes
  média), jamais lu par l'appli Python elle-même.
- `HOST_LIBRARY_ROOT` : dossier hôte large monté dans `app` + les *arr +
  Jellyfin, sert de racine pour tout dossier ajouté depuis l'UI.
- `SHARES_MOUNT` : dossier technique où l'app monte les partages SMB
  ajoutés depuis l'UI (`mount -t cifs`), monté avec propagation `shared`
  côté `app` et `rslave` côté *arr/Jellyfin (pour qu'un mount créé après le
  démarrage des conteneurs — cas normal via l'UI — leur soit bien propagé).

`HOST_LIBRARY_ROOT` et `SHARES_MOUNT` sont uniquement des variables **hôte**,
consommées par `docker-compose.yml` (interpolation `${...}`, résolue avant le
démarrage des conteneurs) et par `install.sh` — jamais injectées dans
l'environnement du conteneur `app` (le service `app` liste explicitement ses
propres variables sous `environment:` dans `docker-compose.yml`, sans
`env_file: .env`) ni lues par l'appli Python. Elles ne doivent surtout pas
devenir des champs `Settings` : `pydantic-settings` est case-insensitive, un
champ `shares_mount`/`host_library_root` serait écrasé par la valeur hôte
(chemins fixes côté conteneur, définis en constantes dans `app/config.py`).

Si vous copiez `.env.example` sans passer par `install.sh`, remplissez
`HOST_LIBRARY_ROOT`/`SHARES_MOUNT` vous-même — laissés vides, `docker compose
up` échoue avec un message peu clair (source de bind mount vide).

Le fichier `.env` lui-même est aussi bind-monté (lecture-écriture) dans `app`
à `/app/.env` : `POST /settings/import` réécrit ce fichier et redémarre
l'appli pour le recharger — sans ce bind mount, l'écriture serait perdue au
redémarrage du conteneur (couche éphémère).

## Build multi-architecture
- `docker buildx build --platform linux/arm64` pour produire l'image depuis
  une machine x86 (évite de builder directement sur le Pi, lent)
- Image de l'appli maison en Alpine, multi-stage, nettoyée,
  `HEALTHCHECK` sur `/health` (cf. ADR 0003) — vise < 150 Mo, mesurée à 99 Mo.
  Le conteneur `app` tourne en root (`CAP_SYS_ADMIN` requis pour
  `mount -t cifs`/`umount` des partages SMB, cf. ADR 0005) — l'utilisateur
  non-root visé par ADR 0003 ne s'applique plus à ce service précis, voir le
  correctif du 2026-08-20 dans cette ADR
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

`backup.sh` archive `sonarr-config`, `radarr-config`, `lidarr-config`,
`readarr-config`, `jellyfin-config`, `calibre-web-config`, et `app-data`
(contient `cache.db` + les comptes utilisateurs) puis les envoie via
`rclone` (exécuté en conteneur Docker jetable — aucune installation de
`rclone` sur l'hôte requise) vers un remote configuré par l'utilisateur —
disque externe (chemin local ou monté), NAS en SSH, ou cloud (S3/B2/Drive/
etc., au choix de `rclone`). La bibliothèque média elle-même n'a pas besoin
d'être sauvegardée si re-téléchargeable via les *arr.

### Configuration initiale (une fois)

1. Configuration interactive du remote de destination (identifiants cloud
   ou chemin disque/SSH selon le choix) :
   ```
   mkdir -p ~/.config/rclone
   docker run --rm -it -v ~/.config/rclone:/config/rclone rclone/rclone config
   ```
2. Ajouter au crontab (`crontab -e`) :
   ```
   0 3 * * * RCLONE_REMOTE=nom:chemin /chemin/vers/backup.sh
   ```
   (adapter `nom:chemin` au remote configuré à l'étape 1, et le chemin vers
   le script à son emplacement réel)

### Rétention

Les sauvegardes de plus de 14 jours sont supprimées automatiquement du
remote après chaque envoi réussi (variable `RETENTION_DAYS`, ajustable).

### Restauration (procédure manuelle)

Pas de script de restauration — enjeu trop élevé pour un script qui devine
en pleine panne. Pour restaurer un service (exemple avec `sonarr`) :

1. Télécharger l'archive datée souhaitée depuis le remote :
   `docker run --rm -v ~/.config/rclone:/config/rclone -v "$(pwd):/data" rclone/rclone copy nom:chemin/AAAA-MM-JJ/sonarr-config.tar.gz /data`
2. Arrêter le service : `docker compose stop sonarr`
3. Vider le volume existant :
   `docker run --rm -v ultimatemediacenter_sonarr-config:/data alpine sh -c "rm -rf /data/*"`
4. Extraire l'archive dans le volume :
   `docker run --rm -v ultimatemediacenter_sonarr-config:/data -v "$(pwd):/backup" alpine tar xzf /backup/sonarr-config.tar.gz -C /data`
5. Redémarrer : `docker compose up -d sonarr`

Adapter le nom de volume/service pour les autres composants
(`radarr`, `lidarr`, `readarr`, `jellyfin`, `calibre-web`, `app`).

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

## Dépannage : propagation des partages SMB

Pour que `propagation: shared`/`rslave` fonctionne (mount créé côté `app`
après l'ajout d'un partage depuis l'UI, visible dans les *arr/Jellyfin sans
redémarrage), le point de montage source du bind (`${SHARES_MOUNT}`, un
simple `mkdir -p` fait par `install.sh`) doit appartenir à un *peer group*
partagé côté hôte. Sur la plupart des distributions Linux récentes avec
systemd, `/` est déjà monté `rshared` par défaut et ça fonctionne sans rien
faire de plus. Si ce n'est pas le cas sur votre hôte (mounts créés depuis
l'UI qui n'apparaissent pas dans les *arr/Jellyfin sans `docker compose
restart`), vérifiez la propagation de `/` :

```
findmnt -o TARGET,PROPAGATION /
```

Si elle n'affiche pas `shared`, rendez le point de montage partagé
manuellement avant `docker compose up` :

```
sudo mount --make-rshared /
```

`install.sh` ne l'automatise pas dans cette itération (pas de mount
bind-sur-lui-même supplémentaire) — cette étape reste manuelle si votre hôte
ne l'a pas déjà par défaut.

## Répartition de charge (si Pi saturé)
- Déporter les *arr sur une seconde machine (NAS, mini-PC) ; le Pi garde
  uniquement `app` + `jellyfin` + `caddy`
- Aucun changement de code nécessaire, seulement les URLs dans la config
