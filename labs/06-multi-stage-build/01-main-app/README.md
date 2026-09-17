# 01-main-app — Task 1 multi-stage application

The assignment's main application. Node.js + Express, listens on **port 8080**, returns exactly
`Hello World from Docker multi-stage build`.

## Files

| File | Purpose |
|---|---|
| `server.js` | Express app binding `0.0.0.0:8080` |
| `package.json` | One production dependency (`express`) plus `eslint`/`jest` as dev dependencies |
| `Dockerfile` | Multi-stage: `builder` installs prod deps, `runtime` copies them onto a clean Alpine base |
| `Dockerfile.single-stage` | Naive single-stage build on the full `node:24` image, for size comparison |

## Build and run

```bash
docker build -t hw06-main-app:multi  -f Dockerfile .
docker build -t hw06-main-app:single -f Dockerfile.single-stage .
docker run -d --name hw06-main-app -p 8080:8080 hw06-main-app:multi
curl -s http://localhost:8080/
```

```text
Hello World from Docker multi-stage build
```

If host port 8080 is already taken, publish on another host port such as `-p 8090:8080` — the container port stays 8080.

## Measured size

| Build | Disk usage | Pull size |
|---|---|---|
| `hw06-main-app:single` | 1.88 GB | 445 MB |
| `hw06-main-app:multi` | 237 MB | 59.7 MB |

**Saving: 1.64 GB on disk (−87.4%), 385 MB per pull (−86.6%).**

The single-stage image carries 288 top-level npm packages including `eslint` and `jest`; the
multi-stage image carries 65 and neither dev tool. Full evidence in the
[parent README](../README.md).
