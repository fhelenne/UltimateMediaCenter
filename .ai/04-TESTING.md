# Tests

## Pyramide de tests
- **Unitaires (majorité)** : logique métier pure — parsing des webhooks, formatage
  des notifs, mapping des statuts *arr → modèle interne
- **Intégration** : appels aux API *arr/Jellyfin mockés (via `respx` ou `responses`)
  pour valider les contrats sans dépendre des services réels
- **End-to-end (minoritaires)** : scénario complet contre des instances *arr/Jellyfin
  de test (docker-compose dédié), lancé en CI ou manuellement avant release

## Outils
- `pytest` + `pytest-asyncio` (FastAPI est async)
- `httpx.AsyncClient` pour tester les endpoints FastAPI sans serveur réel
- Couverture : `pytest-cov`, seuil minimum à définir (ex. 80% sur le code métier,
  hors code de câblage/config)

## Cas critiques à couvrir en priorité
- Webhook reçu avec payload malformé → ne doit jamais crasher l'appli
- Webhook rejoué (même event) → pas de notif dupliquée
- *arr injoignable → l'UI doit rester utilisable en mode dégradé
- Re-match manuel → bon *arr appelé selon le type de média

## Tests de charge (léger, adapté au Pi)
Vérifier que l'appli reste réactive avec plusieurs webhooks quasi simultanés
(rafale de sortie d'épisodes un même soir). Pas de tests de charge lourds
nécessaires vu le contexte mono-foyer.

## CI
- Pipeline GitHub Actions : lint → tests unitaires → tests d'intégration → build image
- Les tests e2e restent manuels ou déclenchés à la demande (coût de setup plus élevé)
