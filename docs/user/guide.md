# Guide utilisateur — UltimateMediaCenter

Point d'entrée unique pour films, séries, musique et livres, avec
notifications de nouveautés et intégration Jellyfin/Kobo. Ce guide couvre
l'usage courant une fois l'installation terminée.

## Première connexion

À la fin de l'installation, un mot de passe admin aléatoire est généré et
affiché **une seule fois**, dans les logs d'installation
(`docker compose logs app` si vous l'avez manqué juste après
`install.sh`).

1. Ouvrir l'URL locale de l'appli (affichée en fin d'installation, en
   général `http://<adresse-du-pi>:8000`)
2. Se connecter avec `admin` et le mot de passe généré
3. Changement de mot de passe **obligatoire** à cette première connexion —
   choisir un nouveau mot de passe, pas besoin de l'ancien pour cette
   étape précise (mais requis pour tout changement ultérieur)

## Naviguer dans la bibliothèque

La page d'accueil propose quatre onglets : **Séries**, **Films**,
**Musique**, **Livres** — un par outil *arr connecté (Sonarr, Radarr,
Lidarr, Readarr).

Chaque onglet affiche deux sections :
- **Queue active** : téléchargements en cours pour ce type de média
- **Bibliothèque** : contenu déjà présent, paginé, avec statut de suivi

Si un service *arr est injoignable, l'onglet l'indique plutôt que de
planter.

## Re-matcher un fichier mal identifié

Quand un fichier est mal associé par l'auto-matching des *arr (mauvais
titre, mauvaise version) :

1. Cliquer sur **Re-match** sur la ligne concernée
2. Choisir la bonne correspondance dans la liste de candidats proposée
   par le *arr concerné
3. Valider — le fichier est réorganisé côté *arr sans quitter l'appli

## Lien Jellyfin

Quand un élément de la bibliothèque est retrouvé dans Jellyfin, un lien
**Voir dans Jellyfin** apparaît à côté du bouton Re-match — ouvre
directement la fiche du média dans Jellyfin pour le lancer.

## Livres numériques et liseuse Kobo

Le pipeline ebooks (scan, enrichissement métadonnées) est automatique dès
qu'un livre est ajouté par Readarr — rien à faire de ce côté.

Pour synchroniser une liseuse Kobo physique, une configuration manuelle
sur l'appareil est nécessaire une fois : voir
[`liseuse-kobo.md`](liseuse-kobo.md).

## Mise à jour

Relancer la même commande d'installation qu'au premier jour — `install.sh`
détecte l'installation existante et bascule automatiquement en mode mise à
jour (récupère le code à jour, reconstruit l'image, redémarre les
services). Le mot de passe admin ne change pas lors d'une mise à jour — il
n'est généré qu'au tout premier démarrage.

## Sauvegardes

Sauvegardes automatiques de la configuration (comptes, config *arr,
Jellyfin, Calibre-web) — mise en place et procédure de restauration :
voir `.ai/05-DEPLOYMENT.md`, section "Sauvegarde".
