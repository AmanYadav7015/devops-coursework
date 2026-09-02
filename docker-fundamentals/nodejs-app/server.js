// Plain Node.js HTTP server - no framework, no npm install required.
const http = require('http');

const PORT = process.env.PORT || 3000;

const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Node.js Hello World</title>
  <style>
    body { font-family: sans-serif; background:#2d3436; color:#dfe6e9; text-align:center; padding-top:80px; }
    h1 { font-size: 3em; color:#00b894; }
    p { color:#b2bec3; }
  </style>
</head>
<body>
  <h1>Hello World</h1>
  <p>Served by a plain <strong>Node.js</strong> HTTP server (node:22-alpine)</p>
  <p>Hostname: ${require('os').hostname()}</p>
</body>
</html>`;

const server = http.createServer((req, res) => {
  res.writeHead(200, { 'Content-Type': 'text/html' });
  res.end(html);
});

server.listen(PORT, () => {
  console.log(`Node.js Hello World server listening on port ${PORT}`);
});
