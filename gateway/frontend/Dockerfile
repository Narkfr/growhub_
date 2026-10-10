# Tableau de bord GrowHub (Next.js).
#
# Le contexte de build est la racine du dépôt : le tableau de bord dépend du
# paquet partagé `packages/growhub-client` par une dépendance `file:`
# (`file:../../packages/growhub-client`), qui doit donc se trouver au même
# endroit relatif dans les deux étapes — d'où l'arborescence /app/packages +
# /app/gateway reproduite à l'identique.
FROM node:20-slim AS builder

WORKDIR /app

# Cible des `rewrites` de next.config.mjs : le service Django du réseau Compose.
ARG GROWHUB_API_URL=http://backend:8000
ENV GROWHUB_API_URL=${GROWHUB_API_URL}

COPY packages/growhub-client ./packages/growhub-client
COPY gateway/frontend/package.json gateway/frontend/package-lock.json ./gateway/frontend/
RUN cd gateway/frontend && npm ci

COPY gateway/frontend ./gateway/frontend
RUN cd gateway/frontend && npm run build

FROM node:20-slim AS runner

WORKDIR /app
ENV NODE_ENV=production

COPY --from=builder /app/packages ./packages
COPY --from=builder /app/gateway/frontend/package.json ./gateway/frontend/package.json
COPY --from=builder /app/gateway/frontend/node_modules ./gateway/frontend/node_modules
COPY --from=builder /app/gateway/frontend/.next ./gateway/frontend/.next
COPY --from=builder /app/gateway/frontend/next.config.mjs ./gateway/frontend/next.config.mjs

WORKDIR /app/gateway/frontend
EXPOSE 3001
CMD ["npm", "start"]
