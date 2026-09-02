# Multi-stage build for the Node.js deployment demo.
#
# Stage 1 "deps": installs production npm dependencies (needs the full
# npm registry client / cache). Stage 2 copies only the resulting
# node_modules + app source into a clean image, so npm's own cache and
# any dev tooling never reach the runtime image.

# ---- Stage 1: deps ----
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json .
RUN npm install --omit=dev --no-audit --no-fund

# ---- Stage 2: runtime ----
FROM node:22-alpine
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY package.json server.js ./

EXPOSE 3000
USER node

CMD ["node", "server.js"]
