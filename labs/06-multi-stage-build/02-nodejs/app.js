const express = require("express");

const app = express();
const PORT = process.env.PORT || 8080;

app.get("/", (req, res) => {
  res.type("text/plain").send("Hello World from Node.js multi-stage build");
});

app.get("/health", (req, res) => {
  res.json({ status: "ok", runtime: "node", version: process.version });
});

app.listen(PORT, "0.0.0.0", () => {
  console.log(`node app listening on port ${PORT}`);
});
