# Node.js Hello World

An Express server that answers `GET /` with `Hello World from Node.js` on port 3000.

## Build

```bash
cd homework/05-docker-hello-world/nodejs-app
docker build -t hw05-nodejs .
```

## Run

```bash
docker run -d --name hw05-nodejs -p 3000:3000 hw05-nodejs
docker ps --filter name=hw05-nodejs
```

## Verify

```bash
curl http://localhost:3000
```

```text
<h1>Hello World from Node.js</h1>
```

Or open <http://localhost:3000> in a browser.

## Clean up

```bash
docker rm -f hw05-nodejs
```
