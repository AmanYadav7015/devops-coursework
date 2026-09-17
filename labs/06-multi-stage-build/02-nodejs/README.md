# 02-nodejs — Node.js multi-stage build

Express app on **container port 8080**, published on host port 8091. Returns
`Hello World from Node.js multi-stage build` and exposes a `/health` JSON endpoint.

## The multi-stage pattern: dependency stage, then runtime

```text
FROM node:24-alpine AS deps
WORKDIR /deps
COPY package.json ./
RUN npm install --omit=dev

FROM node:24-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production
COPY --from=deps /deps/node_modules ./node_modules
COPY app.js package.json ./
EXPOSE 8080
CMD ["node", "app.js"]
```

The `deps` stage resolves and installs the dependency tree. Only the resolved `node_modules` directory
crosses into the runtime stage — npm's cache, its temp files and the dev dependencies (`eslint`,
`jest`, `typescript`) stay behind. `package.json` is copied before the install so that changing
`app.js` does not invalidate the cached `npm install` layer.

## Build, run, verify

```bash
docker build -t hw06-node:multi  -f Dockerfile .
docker build -t hw06-node:single -f Dockerfile.single-stage .
docker run -d --name hw06-node -p 8091:8080 hw06-node:multi
docker logs hw06-node
curl -s http://localhost:8091/
curl -s http://localhost:8091/health
```

```text
node app listening on port 8080
Hello World from Node.js multi-stage build
{"status":"ok","runtime":"node","version":"v24.21.0"}
```

## Measured size

| Build | Base image | Disk usage | Pull size |
|---|---|---|---|
| `hw06-node:single` | `node:24` (Debian) | 1.91 GB | 454 MB |
| `hw06-node:multi` | `node:24-alpine` | 237 MB | 59.7 MB |

**Saving: 1.67 GB on disk (−87.6%), 394 MB per pull (−86.8%).**
