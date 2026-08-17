# Configurer la synchronisation Kobo

Cette étape est **manuelle, côté liseuse** — elle n'est pas gérée par
`install.sh`. Elle ne se fait qu'une fois par appareil.

## Pré-requis
- Le serveur média est installé et lancé (`docker compose up -d`)
- Le pont Calibre-web répond : vérifier que
  `http://<adresse-du-pi>:8000/opds/` retourne un catalogue, et que
  `http://<adresse-du-pi>:8000/web/` retourne bien une erreur 404 (voir
  `.ai/05-DEPLOYMENT.md`, section "Vérification pont Calibre-web")
- La liseuse Kobo est connectée au même réseau Wi-Fi que le serveur

## Étapes sur la liseuse

1. Connecter la Kobo au Wi-Fi (Réglages → Wi-Fi)
2. Faire une synchronisation normale une première fois (bouton
   "Synchroniser" en page d'accueil), pour que l'appareil génère ses
   identifiants internes de sync
3. Ouvrir le navigateur intégré de la Kobo (icône Chrome/navigateur,
   accessible depuis le magasin Kobo ou un raccourci navigateur — selon
   firmware) et se rendre sur :
   ```
   http://<adresse-du-pi>:8000/kobo/<TOKEN>
   ```
   Le `<TOKEN>` est généré par Calibre-web pour cet utilisateur — le
   récupérer une seule fois via le connecteur : suivre la procédure Kobo
   Sync de Calibre-web pour obtenir l'URL complète pré-remplie avec le
   token (ce token n'est jamais exposé par notre appli — Calibre-web est
   la seule source, cf. ADR 0004)
4. La page confirme le changement d'URL de sync et invite à relancer une
   synchronisation manuelle
5. Retourner en page d'accueil de la Kobo, lancer "Synchroniser" — la
   bibliothèque doit apparaître

## Vérifications après configuration
- Un livre ajouté côté Readarr (donc scanné/enrichi par `calibredb`, cf.
  Phase 5a) apparaît sur la Kobo après une synchronisation manuelle
- Le statut de lecture (page courante, terminé) se met à jour côté
  Calibre-web après lecture sur la liseuse — pas remonté dans l'UI de
  l'appli pour l'instant (amélioration possible, cf. ADR 0004,
  Conséquences)

## En cas de problème
- Si la sync échoue silencieusement : vérifier d'abord que `/kobo/*`
  répond bien via Caddy (`curl -I http://<adresse-du-pi>:8000/kobo/`) —
  un problème réseau/proxy est la cause la plus fréquente, pas un
  problème côté liseuse
- Si le token a été perdu ou invalidé : régénérer via Calibre-web (accès
  admin uniquement, l'UI `/web` de Calibre-web n'étant pas exposée
  publiquement) et refaire les étapes 3-5
- Cette configuration est spécifique à chaque appareil : une nouvelle
  liseuse ou une réinitialisation de la Kobo demande de refaire ces
  étapes
