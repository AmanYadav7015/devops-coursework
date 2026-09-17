const express = require("express");

const app = express();
const PORT = process.env.PORT || 8080;

app.get("/", (req, res) => {
  res.type("text/plain").send("Hello World from Docker multi-stage build");
});

app.listen(PORT, "0.0.0.0", () => {
  console.log(`main-app listening on port ${PORT}`);
});
