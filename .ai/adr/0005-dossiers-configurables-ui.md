# ADR 0005 — Dossiers de bibliothèque configurables depuis l'UI (local + SMB)

**Statut** : proposé
**Date** : 2026-08-20

## Contexte
Jusqu'ici, chaque catégorie (séries/films/musique/livres) est liée à un seul
dossier fixe (`${USB_MOUNT}/tv`, etc.), défini une fois à l'installation via
`install.sh`. L'utilisateur veut pouvoir ajouter/retirer des dossiers par
catégorie après coup, sans réinstaller — y compris des dossiers hors du
disque USB (n'importe où sur l'hôte) et des partages réseau SMB, gérés
directement depuis l'interface (identifiants inclus), pas via l'OS.

Contrainte : Docker fige les points de montage d'un container à sa création.
Une UI ne peut pas faire apparaître un nouveau chemin hôte à l'intérieur
d'un container déjà démarré sans un composant capable d'agir sur les mounts
du système hôte.

## Options considérées
1. **Piloter Docker depuis l'app** (socket Docker monté dans `app`,
   recréation de service à chaque ajout de dossier) — donne à `app` un accès
   quasi-root à l'hôte via l'API Docker, coupe le service concerné à chaque
   changement, complexité d'orchestration (fichiers compose générés à la
   volée). Écarté : trop lourd, trop risqué pour un gain modeste.
2. **Montage large + `app` privilégié pour les mounts CIFS** (retenue) —
   `app` monte un dossier hôte large (le home de l'utilisateur, choisi à
   l'installation) et tous les *arr/Jellyfin le montent aussi, en lecture-
   écriture, sans privilège. Pour SMB, `app` seul devient privilégié
   (`SYS_ADMIN` + bind mount à propagation `shared`) et exécute les `mount
   -t cifs` demandés depuis l'UI ; la propagation `shared` rend le mount
   visible côté hôte, donc automatiquement visible dans les autres
   containers qui partagent le même dossier hôte.
3. **Montage manuel par l'utilisateur (fstab)** — zéro risque supplémentaire,
   mais contredit l'exigence explicite : gestion doit se faire depuis l'UI,
   identifiants inclus.

## Décision
Option 2. `app` — déjà le container le plus exposé (derrière Caddy) —
devient le seul composant privilégié du stack, avec capacité `SYS_ADMIN` et
`cifs-utils` installé. Les autres *arr/Jellyfin restent non-privilégiés et
n'héritent que de la visibilité des mounts, jamais du contrôle.

Une fois un dossier (local ou SMB) monté et visible, `app` l'enregistre via
l'API root-folder déjà exposée par chaque *arr (et l'API bibliothèque de
Jellyfin) — on ne réimplémente pas leur gestion de médiathèque, seulement
la visibilité du chemin.

## Conséquences
- Compromission de `app` = accès complet au système de fichiers hôte (pas
  seulement aux dossiers médias). C'est un changement de posture de
  sécurité assumé, documenté dans le guide utilisateur.
- Identifiants SMB stockés en clair dans SQLite (cohérent avec les secrets
  déjà en clair dans `.env`/`install.log`, cf. mémoire `install_sh_state`) —
  pas de chiffrement dans une première version, à documenter comme dette.
- Les mounts CIFS ne survivent pas à un redémarrage de container : `app`
  doit remonter tous les partages enregistrés à son démarrage (nouvelle
  étape de lifespan).
- `docker-compose.yml`, `install.sh` (prompt du dossier racine local à
  monter) et `.ai/02-ARCHITECTURE.md`/`05-DEPLOYMENT.md` doivent refléter
  cette décision une fois implémentée.
