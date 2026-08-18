# Plan de développement

## Phase 0 — Cadrage (avant code)
- [ ] Valider la stack (frontend SSR vs SPA, cf. ADR 0001)
- [ ] Installer et configurer manuellement Sonarr/Radarr/Jellyfin/ntfy en local
      pour comprendre leurs API avant de les orchestrer
- [ ] Définir le schéma de données interne (média, statut, événement)

## Phase 1 — MVP : notifications
Objectif : bout en bout fonctionnel sur le flux le plus simple.
- [ ] Endpoint webhook `/webhook/sonarr` fonctionnel
- [ ] Parsing de l'event + envoi vers ntfy
- [ ] Tests unitaires sur le parsing + tests d'intégration mockés
- [ ] Déploiement docker-compose sur le Pi (app + ntfy + Sonarr de test)
- **Critère de sortie** : une sortie d'épisode dans Sonarr déclenche une vraie
  notif sur le téléphone

## Phase 2 — Extension aux autres *arr
- [ ] Webhooks Radarr, Lidarr, Readarr (même pattern que Sonarr)
- [ ] Déduplication des events rejoués
- [ ] Adaptateur de notif interchangeable (ntfy/Telegram/Gotify)

## Phase 3 — Orchestrateur + UI unifiée
- [x] Client API pour chaque *arr (lecture seule au départ : liste, statut)
- [x] UI listant les médias suivis avec statut agrégé
- [x] Cache court pour limiter les appels aux *arr

## Phase 4 — Re-match manuel
- [x] Action UI → Manual Import côté *arr concerné
- [x] Toggle metadata locale Jellyfin via son API
- [x] Tests couvrant les cas d'erreur (mauvais type de média, *arr injoignable)

## Phase 5 — Intégration lecture
- [x] Intégration Jellyfin dans l'UI (lien direct ou embed du player)
- [x] Pipeline ebooks : `calibredb add` + `fetch-ebook-metadata` pour scan,
      enrichissement et organisation (indépendant de Calibre-web)
- [x] Calibre-web déployé en pont protocole seul — `/kobo/*` + `/opds/*`
      exposés via reverse proxy, `/web` bloqué (ADR 0004)
- [x] Documentation de la configuration liseuse (changement d'URL de sync côté
      appareil — action manuelle, hors script d'installation)

## Phase 6 — Durcissement
- [x] Authentification par session cookie + compte admin par défaut, changement
      de mot de passe forcé à la première connexion (ADR 0002)
- [x] Image Docker de l'appli en Alpine multi-stage, nettoyée, < 150 Mo (ADR 0003)
- [x] Sauvegardes automatisées (config *arr, DB app)
- [x] Script d'installation one-liner (`install.sh`), idempotent, testé sur
      Raspberry Pi OS vierge — cf. `05-DEPLOYMENT.md`
- [ ] Documentation utilisateur finale + procédure de mise à jour

## Interface — décision actée
SSR + HTMX retenu (ADR 0001). Prévoir tout de même une maquette basse fidélité
des écrans principaux (liste médias, statut, re-match) avant d'attaquer la
Phase 3, pour clarifier les partiels HTMX nécessaires avant de coder.

## Notes de méthode
- Chaque phase = une branche + une PR, revue avant merge (cf. QUALITY.md)
- Tester sur le Pi réel dès la phase 1, pas seulement en dev x86 — les
  contraintes RAM/CPU se voient tôt
- Ne pas paralléliser les phases 2 à 4 en solo : elles partagent le même
  pattern, autant le solidifier une fois avant de dupliquer
