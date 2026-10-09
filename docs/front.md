# Front (tableau de bord)

Application **Next.js (App Router) + React 19 + TypeScript** dans
`gateway/frontend/`. Elle ne parle qu'à l'API v1 et ne contient aucune règle
métier : les droits, la propriété et les commandes sont tranchés côté serveur.

## Le paquet partagé `@growhub/client`

`packages/growhub-client/` contient les types de l'API et le client HTTP. C'est
le seul endroit où l'API est décrite côté client, ce qui permet :

- au tableau de bord de l'utiliser directement ;
- à une future application React Native de s'y brancher sans réécrire les
  appels ni les types.

Le paquet est livré **en source TypeScript** (pas d'étape de build) : Next le
compile via `transpilePackages`, Metro fera de même côté mobile. Il n'a aucune
dépendance d'exécution : `fetch` est injecté (avec repli sur le `fetch` global),
le jeton CSRF est lu dans le cookie seulement s'il y a un `document`, et le flux
temps réel tombe en sondage quand `EventSource` n'existe pas — c'est ce qui rend
un seul client utilisable par les deux applications.

```ts
import { GrowHubClient } from '@growhub/client';

const client = new GrowHubClient({ baseUrl: '' });      // même origine
const devices = await client.listDevices();
await client.sendCommand(12, 'actuators', 'on', { target: 'WaterPump' });
const stop = client.subscribeLive((snapshot) => console.log(snapshot.count));
```

## Authentification

Session Django. `POST /api/v1/auth/login` ouvre la session ; `GET
/api/v1/auth/me` renvoie le profil **et pose le cookie `csrftoken`** dont la SPA
a besoin pour tout appel non sûr (DRF refuse un POST en session sans
`X-CSRFToken`). Le client ajoute l'en-tête automatiquement.

`NEXT_PUBLIC_API_URL` est vide par défaut : les appels passent par la même
origine et Next proxifie `/api/*` vers le backend (`next.config.mjs`), ce qui
garde le cookie en first-party.

## Pages

| Route | Rôle |
| :--- | :--- |
| `/login` | connexion |
| `/` | Bourgeons de l'utilisateur, état temps réel, accès à l'appairage |
| `/pair` | saisie du code affiché sur l'écran du boîtier |
| `/devices/[id]` | mesures, actionneurs, configuration (propriétaire), historique, partage |

L'état temps réel vient du flux SSE du serveur (rafraîchissement toutes les 2 s)
avec repli en sondage : les écrans consomment les deux sans le savoir.

## Tests et vérifications

```bash
cd packages/growhub-client && npm run typecheck && npm test   # types + client API
cd gateway/frontend        && npx tsc --noEmit && npm test    # logique d'affichage
npx next build                                                # les pages compilent
```

La CI exécute les trois (jobs « Client partagé » et « Front »).

Limite assumée à ce stade : les tests du front portent sur la logique pure
(formatage, fraîcheur, lecture d'un instantané) et sur le client partagé, pas
encore sur les composants React — à trancher au jalon M9 quand les écrans
auront cessé de bouger.
