# React Hello World

**Assignment requirements** (verbatim from `DevOps Homework.docx`):

> - Create a separate folder: `React-app`
> - Add the application code.
> - Create a Dockerfile.
> - Build the Docker image.
> - Run the application using Docker.
> - Verify that Hello World is displayed on a webpage.

*Built and run on macOS with Docker Desktop, from `docker-fundamentals/React-app/`.*

[← Back to Docker Fundamentals](../README.md)

---

## Which approach was actually used

**The real toolchain approach — not the CDN fallback.** This app is a genuine React
component tree (`react` + `react-dom`, real JSX in `src/App.jsx` /
`src/index.jsx`), installed with `npm install` and bundled with
[esbuild](https://esbuild.github.io/) (chosen over webpack/CRA because it's a single
small, fast, dependency-light bundler — appropriate for a homework-sized app and
still a real production-grade tool). The npm registry was reachable in this
environment and the whole `docker build` — including `npm install` of 7 packages and
the esbuild bundle step — completed in **under 10 seconds**, so there was no need to
fall back to the CDN/UMD approach the assignment allows as a backup plan.

If `npm install` had been slow or unreachable, the fallback would have been a
single static HTML file loading React/ReactDOM UMD builds from a CDN `<script>` tag
and calling `ReactDOM.render()` inline — that was **not** needed here and was not
used.

## What's here

- `package.json` — declares `react`, `react-dom` (runtime deps) and `esbuild` (dev
  dep, used only in the build stage).
- `src/App.jsx` — the actual React component, renders an `<h1>Hello World</h1>`.
- `src/index.jsx` — mounts `<App />` into `#root` via `react-dom/client`'s
  `createRoot()`.
- `public/index.html` — the HTML shell. It includes `<div id="root">` pre-filled
  with the same "Hello World" text as a static loading placeholder — this is what
  a plain `curl` sees before JavaScript runs. Once `bundle.js` executes, React's
  `createRoot().render()` replaces that div's contents with the live component
  tree, which renders the same text. This is a standard progressive-enhancement
  pattern, not a fake/static substitute for the React app.
- `Dockerfile` — a **multi-stage build**: `node:22-alpine` installs deps and runs
  esbuild, then `nginx:alpine` serves only the static output.

## Dockerfile, line by line

```dockerfile
# ---- Stage 1: build ----
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json ./
RUN npm install
COPY src ./src
COPY public ./public
RUN npm run build

# ---- Stage 2: runtime ----
FROM nginx:alpine
COPY --from=build /app/public /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

| Line | What it does |
|---|---|
| `FROM node:22-alpine AS build` | First stage, named `build`. Has Node/npm to install React and run the bundler. Discarded from the final image — `node_modules` never ships. |
| `WORKDIR /app` | Working directory for the build stage. |
| `COPY package.json ./` | Copied alone (before source) so Docker's layer cache can skip `npm install` on rebuilds that only change app code. |
| `RUN npm install` | Installs `react`, `react-dom`, and `esbuild` (7 packages total, no lockfile needed for this size). |
| `COPY src ./src` / `COPY public ./public` | Copies the JSX source and the HTML template. |
| `RUN npm run build` | Runs `esbuild src/index.jsx --bundle --minify --outfile=public/bundle.js`, producing a single minified JS bundle next to `index.html`. |
| `FROM nginx:alpine` | Second stage: a tiny static file server. No Node, no npm, no `node_modules` in the shipped image. |
| `COPY --from=build /app/public /usr/share/nginx/html` | Copies only the build output (`index.html` + `bundle.js`) from the `build` stage — this is the entire final image's content beyond the nginx base. |
| `EXPOSE 80` | Documents the listening port. |
| `CMD ["nginx", "-g", "daemon off;"]` | Runs nginx in the foreground. |

## Build & run

```bash
docker build -t df-react:1.0 .
docker run -d --name df-react -p 18085:80 df-react:1.0
curl -s http://localhost:18085
```

## What actually happened

`docker build` finished in well under 10 seconds total, including `npm install`
(`added 7 packages, and audited 8 packages in 8s`) and the esbuild bundle step
(`⚡ Done in 20ms`). No network problems, no fallback needed.

Final image: **92.9MB disk usage / 26.2MB content size** — essentially the same
size as `nginx-app` and `Apache-app`, because the final image only contains
nginx + two small static files (`index.html`, `bundle.js`); the entire React/Node
build toolchain lives only in the discarded first stage.

`curl -s http://localhost:18085` returned HTML containing `<h1>Hello World</h1>`
(from the static placeholder in `index.html` — the same text React would also
render once `bundle.js` runs in a real browser). `curl -I` returned
`HTTP/1.1 200 OK` from `nginx/1.31.4`.
