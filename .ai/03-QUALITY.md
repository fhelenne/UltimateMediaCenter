# Qualité

## Style de code
- **Python** : PEP8, formaté avec `ruff format`, linté avec `ruff check`
- **Typing** : type hints obligatoires sur toutes les fonctions publiques,
  vérifiés avec `mypy` (mode strict progressif)
- **Docstrings** : format Google, obligatoires sur modules/classes publiques

## Convention de commits
- [Conventional Commits](https://www.conventionalcommits.org/) :
  `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`
- Un commit = un changement logique, message à l'impératif

## Revue de code
- Toute modification passe par une Pull Request, même en solo (historique propre)
- Checklist PR : tests passants, lint clean, doc mise à jour si API modifiée

## Gestion des secrets
- Aucun secret en clair dans le repo (clés API *arr, tokens ntfy)
- `.env` local + `.env.example` versionné, chargé via `pydantic-settings`

## Observabilité
- Logs structurés (JSON) avec niveau configurable
- Endpoint `/health` pour vérifier la disponibilité de l'orchestrateur et des *arr

## Gestion des erreurs
- Timeouts explicites sur tous les appels aux API externes (*arr, Jellyfin)
- Circuit breaker simple : *arr injoignable → UI affiche un statut dégradé, ne plante pas

## Dette technique
- Fichier `TODO.md` ou labels GitHub `tech-debt` pour tracer les compromis pris
  volontairement (ex : cache naïf en v1, à améliorer en v2)
