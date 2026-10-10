# Déploiement continu — growhub_

Ce document décrit la chaîne en place depuis le 2026-10-10 : ce qui se passe quand
`main` bouge, comment déployer ou revenir en arrière à la main, et ce que le
pipeline ne touche jamais.

## La chaîne

```
push sur main
   └─ CI (lint, pytest, client, front)          .github/workflows/ci.yml
        └─ verdict vert
             └─ Deploy                            .github/workflows/deploy.yml
                  └─ runner auto-hébergé « pi-growhub » (sur le Pi)
                       └─ ~/growhub_/tools/deploy.sh
```

Le déploiement **ne part pas** si la CI est rouge, et il ne part pas non plus
depuis une autre branche : la condition porte sur le verdict du workflow « CI » et
sur `head_branch == main`. Il déploie la révision exacte que la CI a validée
(`head_sha`), pas « ce qu'il y a sur main à ce moment-là ».

## L'hôte et le runner

- Le runner tourne **sur le Pi**, en service utilisateur :
  `systemctl --user status github-runner`. Aucun accès entrant n'est nécessaire,
  aucune clé SSH n'existe pour déployer, et la construction se fait sur place —
  ce qui compte, le Pi étant ARM64 là où les runners GitHub sont x86.
- Il est enregistré sous le nom `pi-growhub` avec le label `growhub-gateway` ;
  c'est ce label que vise le travail (`runs-on: [self-hosted, growhub-gateway]`).
- `loginctl enable-linger marius` est activé : le runner repart au démarrage de la
  machine, sans session ouverte.
- Il exécute le contenu de `main` : n'importe quel commit mergé sur `main` peut
  faire tourner du code sur cette machine. C'est voulu ici (dépôt personnel, une
  seule personne qui merge) ; sur un dépôt où des inconnus ouvrent des PR, il
  faudrait une approbation obligatoire sur les PR venues d'un fork.

## Ce que fait `tools/deploy.sh`

1. Refuse de travailler si `~/growhub_` porte des modifications non validées.
2. Note la révision en place, récupère `origin`, puis se place sur la révision
   demandée (la branche `main` si c'est elle, sinon un état détaché — le script ne
   déplace jamais une branche vers une révision arbitraire).
3. Lance `tools/backup.sh` : **avant** toute migration, parce que git ne sait pas
   défaire un changement de schéma. Rotation 7 jours dans `~/growhub_backups`.
4. `docker compose up -d --build --remove-orphans` — l'option `--remove-orphans`
   évite qu'un service renommé laisse un conteneur derrière lui, tenant un port.
5. `manage.py migrate --noinput`, dans le conteneur.
6. Contrôle de santé, qui doit répondre sur le service et pas sur un code de
   sortie : page du tableau de bord en 200, API qui répond (200/401/403), les six
   services en marche, et un avertissement — non bloquant — si plus aucun Bourgeon
   n'a parlé depuis cinq minutes.
7. Écrit la révision précédente dans `~/growhub_backups/deploy-state`, journalise
   dans `~/growhub_backups/deploy.log`.

En cas d'échec du contrôle de santé : retour à la révision précédente, `up` +
`migrate` de nouveau, contrôle rejoué. La sortie est non nulle dans tous les cas
où la pile n'est pas saine à la fin — un déploiement vert qui laisse l'API à terre
serait pire qu'un échec franc.

## À la main

```bash
~/growhub_/tools/deploy.sh                 # déployer main
~/growhub_/tools/deploy.sh -n              # voir ce qui serait fait, sans rien toucher
~/growhub_/tools/deploy.sh --ref <sha>     # déployer (ou revenir à) un commit précis
cat ~/growhub_backups/deploy-state         # la révision précédente
tail -40 ~/growhub_backups/deploy.log      # ce qui s'est passé
```

Dans GitHub → Actions → **Deploy** → *Run workflow*, le champ `ref` fait la même
chose à distance (retour arrière sans se connecter au Pi).

## Revenir en arrière — deux choses distinctes

- **Le code** : `--ref <sha>` sur la révision précédente (`deploy-state` la
  contient), ou le travail *Deploy* lancé à la main. Le retour automatique après
  un contrôle de santé en échec fait exactement cela.
- **La base** : un retour de code **ne défait pas** une migration. Si le problème
  vient du schéma, il faut restaurer le dump écrit juste avant le déploiement :

  ```bash
  gunzip -c ~/growhub_backups/growhub-<horodatage>.sql.gz \
    | docker exec -i gateway-postgres-1 psql -U growhub -d growhub
  ```

## Restaurer les identifiants

Le système n'utilise que la visibilité du dépôt : le runner est enregistré avec un
jeton de courte durée obtenu via `gh`, et aucun secret n'est stocké côté GitHub
pour ce déploiement — il n'y a donc rien à faire tourner. Le jour où le jeton du
runner expire ou que la machine est réinstallée :

```bash
cd ~/actions-runner
TOKEN=$(gh api -X POST repos/Narkfr/growhub_/actions/runners/registration-token --jq .token)
./config.sh --url https://github.com/Narkfr/growhub_ --token "$TOKEN" \
  --name pi-growhub --labels growhub-gateway --work _work --unattended --replace
systemctl --user restart github-runner
```

## Ce que le pipeline ne touche jamais

`gateway/.env`, `gateway/mosquitto/config/password_file`, l'ACL, les volumes, le
firmware du boîtier et `~/growhub_backups`. Le déploiement ne remplace que du
code : les secrets et les données restent sur la machine et hors de git.

## Limites connues

- La construction prend quelques minutes sur le Pi (le tableau de bord est la
  partie lente). Ce n'est pas une file d'attente bloquante : `concurrency` ne
  laisse qu'un déploiement à la fois et n'annule jamais celui en cours.
- Un déploiement interrompt brièvement les services recréés ; l'ingestion MQTT
  reprend au redémarrage du worker. Les mesures du boîtier pendant cette fenêtre
  sont perdues (QoS 0, pas de file d'attente côté serveur).
- Le runner n'est pas mis à jour tout seul : reprendre la procédure
  d'enregistrement ci-dessus avec la nouvelle version téléchargée suffit.
