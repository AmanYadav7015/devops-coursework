# React Hello World

A Vite + React single-page app. The Dockerfile is multi-stage: Node builds the static bundle, then the
bundle is copied into an Nginx image. The final image contains no Node.js and no `node_modules`.

Because React renders in the browser, `curl` on `/` returns the HTML shell, not the heading. The
heading text lives inside the compiled JavaScript bundle, which is why the verify step greps the asset.

## Build

```bash
cd homework/05-docker-hello-world/react-app
docker build -t hw05-react .
```

This stage runs `npm install`, so the build needs internet access.

## Run

```bash
docker run -d --name hw05-react -p 8082:80 hw05-react
docker ps --filter name=hw05-react
```

## Verify

```bash
curl http://localhost:8082
```

```text
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>React Hello World</title>
  <script type="module" crossorigin src="/assets/index-DPNYE6g9.js"></script>
</head>
<body>
    <div id="root"></div>
</body>
</html>
```

Confirm the rendered text is really in the bundle:

```bash
curl -s http://localhost:8082/assets/index-DPNYE6g9.js | grep -o 'Hello World from React'
```

```text
Hello World from React
```

Open <http://localhost:8082> in a browser to see `Hello World from React` rendered.

## Clean up

```bash
docker rm -f hw05-react
```
