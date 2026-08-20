# UltimateMediaCenter

Media center auto-hébergé sur Raspberry Pi, unifiant films, séries, musique
et ebooks dans une interface unique — automatisation déléguée à Sonarr,
Radarr, Lidarr, Readarr, lecture via Jellyfin.

## Installation

Sur un Raspberry Pi OS 64 bits vierge :

```bash
curl -sSL https://raw.githubusercontent.com/fhelenne/UltimateMediaCenter/main/install.sh | bash
```

Installe Docker automatiquement si absent, génère les secrets, démarre la
stack, affiche l'URL et le mot de passe admin initial en fin
d'installation — aucun pré-requis à installer soi-même.

## Fonctionnalités

- Vue unifiée Séries / Films / Musique / Livres avec statut de suivi
- Notifications de nouveautés (ntfy)
- Re-match manuel quand l'auto-matching se trompe
- Lien direct vers Jellyfin depuis la bibliothèque
- Pipeline ebooks automatique + synchronisation Kobo (Calibre-web)
- Sauvegardes automatisées vers un remote au choix (`backup.sh`)

## Documentation

- [`docs/user/guide.md`](docs/user/guide.md) — guide utilisateur
- [`docs/user/liseuse-kobo.md`](docs/user/liseuse-kobo.md) — config liseuse Kobo
- [`.ai/`](.ai/) — documentation projet (architecture, déploiement, ADR)

## Stack technique

Python / FastAPI / HTMX, SQLite, Docker Compose. Cible Raspberry Pi 3 B+
(1 Go RAM) — voir `.ai/01-CONTEXT.md` pour les contraintes complètes.
