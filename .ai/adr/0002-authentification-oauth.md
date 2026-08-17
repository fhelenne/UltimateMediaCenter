# ADR 0002 — Authentification OAuth + compte admin par défaut

**Statut** : accepté
**Date** : 2026-08-15

## Contexte
Le projet doit rester utilisable en local (installation one-liner) tout en
supportant un accès distant potentiel (téléphone hors réseau domestique).
Il faut aussi un premier accès simple juste après installation, sans étape
manuelle de création de compte avant de pouvoir se connecter.

## Options considérées
1. **Token statique local** (fichier `.env`, pas de vraie session)
   - Avantages : trivial à implémenter
   - Inconvénients : pas de gestion multi-utilisateur, pas de révocation propre,
     mauvais candidat si accès distant envisagé
2. **OAuth (ex. via Authlib + fournisseur externe ou OAuth interne type
   password grant)**
   - Avantages : standard, révocation de session possible, extensible à un
     accès distant sécurisé (reverse proxy + TLS), compatible avec un futur
     multi-utilisateur
   - Inconvénients : plus de code à écrire et à tester qu'un token statique

## Décision
**OAuth**, avec un compte `admin` créé automatiquement à l'installation
(mot de passe aléatoire généré par `install.sh`, affiché une seule fois en fin
d'install). À la première connexion, changement de mot de passe **obligatoire**
avant tout accès au reste de l'application.

> **Correctif (Phase 6a, implémentation)** : le terme « OAuth » ci-dessus
> décrivait l'intention initiale, pas le flux réellement implémenté. En
> pratique, pour une appli mono-utilisateur strictement locale, un vrai flux
> OAuth2 (grant, tokens, provider) n'apportait rien — c'est une session
> cookie signée (Starlette `SessionMiddleware`, cookie de session serveur,
> pas de token porteur) qui a été retenue. Le principe de la décision (compte
> admin auto-créé, changement de mot de passe forcé à la première connexion)
> reste inchangé, seul le mécanisme de session diffère de la description
> d'origine.

## Conséquences
- Le script `install.sh` génère le mot de passe admin initial et l'écrit dans
  les logs d'install (cf. `05-DEPLOYMENT.md`), jamais en clair dans `.env` versionné
- Endpoint `/auth/change-password` : force la redirection tant que le flag
  `must_change_password` est vrai en base
- Tests dédiés : connexion avec mot de passe par défaut → redirection forcée ;
  tentative de contournement direct d'une route protégée → refusée
- Prépare le terrain pour un accès distant futur sans tout refondre

## Suivi
- Détail technique (bibliothèque OAuth précise, stockage des tokens) à
  préciser en Phase 1, pas figé par cet ADR
- Décision technique complète de l'implémentation (session cookie signée
  plutôt qu'OAuth2, scrypt plutôt que bcrypt pour le hash, stockage de la
  session côté cookie uniquement, etc.) :
  `docs/superpowers/specs/2026-08-17-phase6-auth-design.md`
