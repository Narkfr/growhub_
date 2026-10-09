# ADR 0003 — Conserver Next.js comme front

Garder le dashboard Next.js existant plutôt qu'une SPA Vite ou Expo.

## Contexte
Le front actuel est déjà React 19 + TypeScript sous Next.js. L'objectif affiché est une
application mobile React Native plus tard.

## Décision
Conserver Next.js (mode standalone), moderniser les dépendances, et extraire le client API
et les types dans un paquet partagé (`packages/shared`) réutilisable par l'app mobile.

## Conséquences
- Zéro migration de front ; les composants restent du React standard.
- Le SSR n'apporte rien ici mais ne bloque rien : le partage de code utile passe par
  les types, le client API et les hooks, pas par les composants d'interface.
- L'app React Native sera un nouveau client du même contrat d'API (jalon ultérieur).
