# backup.sh — sauvegardes automatisées — Design

**Statut** : validé, en attente de plan d'implémentation
**Date** : 2026-08-18
**Réfs** : `.ai/DEVELOPMENT_PLAN.md` Phase 6, `.ai/05-DEPLOYMENT.md` section
"Sauvegarde"

## Contexte

`05-DEPLOYMENT.md` décide déjà *quoi* sauvegarder ("config des *arr + config
Jellyfin + base de l'appli, hors du Pi") mais jamais *comment* — "autre
disque ou cloud perso" reste vague. Ce document précise le mécanisme
concret.

## Décisions

### Destination : `rclone` vers un remote configurable

`rclone` couvre les deux cas ("autre disque" via un remote local/SSH, ou
"cloud perso" via S3/B2/Drive/etc.) à travers un seul mécanisme — le script
ne sait pas et n'a pas besoin de savoir quel type de destination l'utilisateur
a choisi. Cohérent avec la convention du projet de déléguer à un outil tiers
plutôt que de réimplémenter (cf. Calibre-web, ADR 0004).

`rclone config` est interactif (identifiants, OAuth pour certains backends)
— **non scriptable**. `backup.sh` suppose donc un remote déjà configuré une
fois par l'utilisateur, référencé via la variable d'environnement
`RCLONE_REMOTE` (ex. `b2:umc-backups`). Étape manuelle documentée, même
nature que la clé API Jellyfin (Phase 6a).

### Déclenchement : cron hôte, pas de conteneur dédié

`backup.sh` est un script autonome, ajouté au crontab de l'hôte par
l'utilisateur (instructions documentées) — **pas** intégré dans
`install.sh`. Deux raisons :
- `install.sh` vient de traverser un cycle complet de revue/correctifs ;
  le rouvrir pour une fonctionnalité qui de toute façon nécessite une
  configuration manuelle post-install (le remote rclone) n'apporte rien
  et ré-ouvre un script déjà validé
- Un conteneur de sauvegarde permanent (type Ofelia) coûterait de la RAM en
  continu sur un Pi 3B+ 1 Go pour une tâche qui ne s'exécute qu'une fois par
  jour — le cron hôte suffit et ne coûte rien entre deux exécutions

Chaque volume de config est archivé via un conteneur `alpine` jetable
montant ce volume en lecture seule — même pattern que `seed_arr_configs`
dans `install.sh`.

### Périmètre : liste du spec + `calibre-web-config`

`sonarr-config`, `radarr-config`, `lidarr-config`, `readarr-config`,
`jellyfin-config`, `app-data` (contient `cache.db` + la table `users`),
plus `calibre-web-config` (jetons de synchronisation Kobo — absent du texte
original du spec, ajouté ici : le perdre force un ré-appairage de chaque
liseuse, coût minime à couvrir puisque le mécanisme est identique).

Volumes média explicitement exclus (re-téléchargeables via les *arr, déjà
acté dans `05-DEPLOYMENT.md`).

### Rétention : 14 jours par défaut, configurable

Non traité dans le texte original du spec, mais une vraie lacune : sans
purge, les sauvegardes s'accumulent indéfiniment sur le remote de
l'utilisateur (coût de stockage cloud, ou saturation d'un disque local).
`backup.sh` supprime les dossiers datés plus vieux que `RETENTION_DAYS`
(défaut 14) après chaque envoi réussi.

### Restauration : documentée, pas de script

Restauration rare, à fort enjeu, bénéficie d'un humain qui lit chaque étape
plutôt que d'un script qui fait des suppositions en pleine crise. Procédure
manuelle documentée dans `05-DEPLOYMENT.md` (télécharger l'archive datée du
remote, arrêter le service concerné, vider le volume Docker, extraire
l'archive dedans, redémarrer). Même choix que `uninstall.sh`, jamais
construit pour la même raison (spec Phase 6, `05-DEPLOYMENT.md`).

### Vérification sans matériel Pi réel

Même approche que pour `install.sh` :
- L'étape de tar par volume s'exécute contre du vrai Docker (disponible
  ici), vérifiable directement
- `rclone` accepte une destination "remote local" sans aucune configuration
  de compte (juste un chemin de dossier) — permet de vérifier tout le flux
  copie + purge de rétention contre un dossier `/tmp` local, sans identifiants
  cloud réels
- Ce que cette vérification ne couvre pas : le comportement réel d'un vrai
  remote cloud (latence réseau, quotas, erreurs d'authentification) — à
  valider manuellement une fois un remote réel configuré

## Flux d'exécution (`backup.sh`)

1. Vérifie `RCLONE_REMOTE` non vide — sinon message clair et sortie (pas
   d'échec silencieux qui remplirait les mails cron d'erreurs cryptiques)
2. Vérifie `docker` et `rclone` présents
3. Crée un répertoire de travail temporaire
4. Pour chaque volume de la liste : conteneur `alpine` jetable, tar
   compressé du contenu vers le répertoire temporaire
5. `rclone copy` du répertoire temporaire vers
   `${RCLONE_REMOTE}/$(date +%Y-%m-%d)/`
6. Purge : liste les dossiers datés sur le remote plus vieux que
   `RETENTION_DAYS`, les supprime
7. Nettoie le répertoire temporaire local
8. Journalise chaque étape avec horodatage dans un fichier de log
   (`backup.log`, même convention que `install.log`)

## Gestion des erreurs

- `set -euo pipefail` — toute étape en échec arrête le script, visible dans
  les logs et dans le mail cron par défaut
- Un volume manquant (nom mal orthographié, service jamais démarré) fait
  échouer tout le run plutôt que de produire silencieusement une sauvegarde
  incomplète — pas de sauvegarde partielle non signalée
- La purge de rétention ne s'exécute qu'après un `rclone copy` réussi —
  jamais de suppression de sauvegardes existantes si l'envoi du jour a échoué

## Fichiers touchés

- Créer : `backup.sh`
- Modifier : `.ai/05-DEPLOYMENT.md` (remplacer la section "Sauvegarde"
  actuelle par le mécanisme concret + procédure de restauration manuelle +
  instructions crontab)
- Modifier : `.ai/DEVELOPMENT_PLAN.md` (cocher l'item une fois fait)

## Hors périmètre

- `install.sh` n'est pas modifié — pas d'intégration automatique du cron
- Script de restauration automatisé
- Support d'un remote autre que ce que `rclone` gère déjà (pas de mécanisme
  de destination maison)
