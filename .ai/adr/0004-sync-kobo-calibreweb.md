# ADR 0004 — Synchronisation liseuse Kobo via Calibre-web

**Statut** : accepté
**Date** : 2026-08-15

## Contexte
La bibliothèque ebooks (alimentée par Readarr) doit être accessible depuis une
liseuse physique, en priorité Kobo, sans dépendre d'un transfert manuel par câble.

## Options considérées
1. **OPDS seul** (catalogue standard, lecture dans un lecteur tiers sur la liseuse)
   - Avantages : standard ouvert, fonctionne avec beaucoup de liseuses/apps
   - Inconvénients : sur un Kobo non modifié, pas de client OPDS natif — nécessite
     un jailbreak ou une app tierce (KOReader) installée sur l'appareil
2. **Kobo Sync (module natif de Calibre-web)**
   - Avantages : simule l'API cloud Kobo officielle — fonctionne sur un Kobo
     stock, sans jailbreak ; synchronise aussi le statut de lecture et les
     collections (pas seulement le téléchargement)
   - Inconvénients : dépend du bon vouloir de Kobo de ne pas changer son API ;
     configuration initiale sur la liseuse un peu technique (modification de
     l'URL de sync)
3. **Réimplémentation maison du protocole Kobo Sync**
   - Avantages : pas de service supplémentaire à orchestrer
   - Inconvénients : protocole non documenté officiellement (reverse-engineered),
     complexité significative (tokens de sync incrémentale, entitlements,
     shelves, statut de lecture, gestion multi-firmware) ; dette de maintenance
     propre si Kobo fait évoluer son API sans préavis ; contrainte GPLv3 si le
     code de Calibre-web est repris comme base plutôt que réimplémenté from
     scratch — écarté, rapport effort/bénéfice défavorable face à un service
     dédié déjà maintenu activement
4. **Transfert manuel (calibre + câble USB)**
   - Écarté : contraire à l'objectif d'automatisation du projet

## Décision
**Calibre-web avec module Kobo Sync activé**, en gardant OPDS actif en
complément pour les autres usages (accès depuis navigateur, autres liseuses).

### Périmètre d'usage précis
Calibre-web tourne **uniquement** comme pont de protocole vers la liseuse
(`/kobo/*` et `/opds/*` exposés via le reverse proxy) — sa propre interface
web (`/web`) reste bloquée, non accessible à l'utilisateur final. Ton appli
FastAPI reste le seul point d'entrée visible.

Le scan, l'enrichissement des métadonnées et l'organisation des fichiers ne
dépendent pas de Calibre-web : ils sont gérés par `calibredb` /
`fetch-ebook-metadata` (CLI du cœur Calibre) et/ou Readarr, en amont, sur la
même bibliothèque. Calibre-web se contente d'indexer cette bibliothèque déjà
organisée pour la resservir au format Kobo Sync/OPDS — aucune fonctionnalité
d'édition ou d'UI de Calibre-web n'est utilisée.

Ce découpage évite toute dépendance à des endpoints internes non garantis de
Calibre-web au-delà de `/kobo` et `/opds`, et ne modifie ni ne redistribue son
code (pas d'implication GPLv3, cf. section Conséquences).

## Conséquences
- Nouveau service `calibre-web` dans le docker-compose (cf. `05-DEPLOYMENT.md`),
  exposé uniquement sur `/kobo/*` et `/opds/*` via le reverse proxy — `/web`
  bloqué
- Pipeline de bibliothèque : Readarr dépose les fichiers → `calibredb add` /
  `fetch-ebook-metadata` scannent, enrichissent et organisent → Calibre-web
  réindexe la même bibliothèque en lecture pour la resservir aux protocoles
  Kobo Sync/OPDS
- Aucune licence à respecter côté ton code : Calibre-web reste un service
  tiers non modifié, appelé via son réseau interne Docker (pas de code repris,
  pas de redistribution — GPLv3 ne s'applique pas à ce mode d'usage)
- Configuration manuelle une fois sur la liseuse (changement d'URL de sync) —
  à documenter clairement dans la doc utilisateur finale, hors périmètre
  du script d'installation automatique (action côté appareil, pas côté serveur)
- Statut de lecture remonté depuis la liseuse peut être exposé dans l'UI de
  ton appli via l'API `/kobo` de Calibre-web (amélioration possible, pas
  obligatoire v1)
