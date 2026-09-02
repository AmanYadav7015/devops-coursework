// Node.js + Express deployment demo (Task 3: Docker Application Deployment).
// Exposes a small JSON API (/api/info) and an HTML page (/), and reports
// the Node.js runtime version and the Express framework version.
const express = require('express');
const os = require('os');

const app = express();
const PORT = process.env.PORT || 3000;
const expressVersion = require('express/package.json').version;

app.get('/api/info', (req, res) => {
  res.json({
    app: 'ms-deploy-node',
    language: 'Node.js',
    runtime: process.version,
    framework: `Express ${expressVersion}`,
    hostname: os.hostname(),
    platform: `${os.type()} ${os.arch()}`,
    timestamp: new Date().toISOString()
  });
});

app.get('/', (req, res) => {
  res.type('html').send(`<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Node.js Deployment Demo</title>
  <style>
    body { font-family: sans-serif; background:#1e272e; color:#d2dae2; text-align:center; padding-top:70px; }
    h1 { font-size: 2.6em; color:#4cd137; }
    p { color:#a4b0be; }
    code { background:#2f3640; padding:2px 8px; border-radius:4px; }
  </style>
</head>
<body>
  <h1>Node.js Deployment Demo</h1>
  <p>Runtime: <strong>${process.version}</strong> &middot; Framework: <strong>Express ${expressVersion}</strong></p>
  <p>JSON API: <code>GET /api/info</code></p>
  <p>Hostname: ${os.hostname()}</p>
</body>
</html>`);
});

app.listen(PORT, () => {
  console.log(`ms-deploy-node listening on port ${PORT} (Node ${process.version}, Express ${expressVersion})`);
});
