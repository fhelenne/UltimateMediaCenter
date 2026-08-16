# ADR 0001 — Interface en SSR (FastAPI + Jinja2 + HTMX)

**Statut** : accepté
**Date** : 2026-08-15

## Contexte
Le frontend doit tourner dans un contexte contraint (Pi 3 B+, 1 Go RAM) et
s'intégrer à une installation one-liner sans étape de build complexe. Deux
options possibles : SPA (ex. React) ou SSR classique.

## Options considérées
1. **SPA (React/Vue)**
   - Avantages : interactivité riche, écosystème large
   - Inconvénients : nécessite une étape de build (webpack/vite) à intégrer
     dans le pipeline d'install ou en CI ; complexité supplémentaire pour un
     bénéfice limité vu le périmètre (peu d'écrans, peu d'utilisateurs simultanés)
2. **SSR pur (Jinja2, rechargement complet à chaque action)**
   - Avantages : le plus simple, zéro JS
   - Inconvénients : UX dégradée pour des actions ponctuelles (re-matcher un
     média) qui rechargeraient toute la page
3. **SSR + HTMX**
   - Avantages : reste léger côté serveur (pas de Node.js sur le Pi), pas de
     build JS à gérer, mises à jour partielles de page (ex. re-match d'une
     carte média sans recharger toute la liste)
   - Inconvénients : moins adapté si l'UI devient très riche en interactions
     complexes (non prévu dans le périmètre v1)

## Décision
**SSR avec FastAPI + Jinja2, interactivité ciblée via HTMX.**

Justification : le Pi 3B+ est la contrainte dimensionnante, pas l'expérience
utilisateur avancée. SSR+HTMX élimine toute étape de build JS du pipeline
d'installation one-liner, garde l'image Docker de l'appli simple à builder en
multi-arch, et couvre largement les besoins d'interactivité identifiés
(listes, statuts, bouton re-matcher).

## Conséquences
- Templates Jinja2 dans `app/templates/`, partiels HTMX pour les fragments
  mis à jour dynamiquement
- Pas de dépendance Node.js dans l'image Docker de l'appli → build plus rapide
  et plus léger, cohérent avec `05-DEPLOYMENT.md`
- Si le besoin d'interactivité évolue fortement en v2 (ex. lecteur intégré
  custom), cette décision devra être révisée dans un nouvel ADR
