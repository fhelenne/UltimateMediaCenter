# Contexte

## Vision
Media center auto-hébergé sur Raspberry Pi 3 B+, unifiant films, séries, musique et
ebooks dans une interface unique, avec automatisation déléguée aux outils *arr
(Sonarr, Radarr, Lidarr, Readarr) et lecture via Jellyfin.

## Problème résolu
- Éviter de jongler entre plusieurs interfaces (Sonarr, Radarr, Jellyfin, Calibre-web...)
- Centraliser les notifications de nouveautés
- Garder la main sur les métadonnées quand l'auto-matching se trompe

## Contraintes techniques
- **Matériel** : Pi 3 B+ — 1 Go RAM, quad-core ARM Cortex-A53, pas de transcodage lourd
- **OS** : Raspberry Pi OS 64-bit (arm64) requis — l'image de l'appli cible
  arm64 uniquement, pas armv7 (ADR 0003)
- **Stockage** : disque externe USB obligatoire (pas la carte SD pour la bibliothèque)
- **Réseau** : usage domestique, pas d'exposition publique par défaut
- **Charge** : les *arr peuvent être déportés sur une autre machine si le Pi sature

## Utilisateurs cibles
- Usage personnel/familial, un ou quelques comptes simultanés
- Pas de multi-tenant, pas de facturation, pas de scalabilité horizontale requise

## Hors périmètre (v1)
- Recodage du matching métadonnées (délégué aux *arr et à Jellyfin)
- Player vidéo/audio maison (délégué à Jellyfin)
- Recherche d'indexeurs torrent/usenet (déléguée aux *arr)

## Dépendances externes
| Service | Rôle |
|---|---|
| Sonarr / Radarr / Lidarr / Readarr | automatisation acquisition + métadonnées |
| Jellyfin | streaming, lecture, agents metadata |
| Calibre-web | pont Kobo Sync/OPDS uniquement — pas d'UI ni d'édition (ADR 0004) |
| ntfy (ou Gotify) | notifications push |
| Indexeurs (torrent/usenet) | source des téléchargements, via *arr |

## Glossaire
- **arr** : famille d'outils Sonarr/Radarr/Lidarr/Readarr
- **Manual Import** : ré-association manuelle d'un fichier à une fiche média
- **Orchestrateur** : couche de ton appli qui agrège les statuts des *arr
