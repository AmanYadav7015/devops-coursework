# Small, official Node LTS image on Alpine Linux (~50MB base)
FROM node:22-alpine

# Set working directory inside the container
WORKDIR /app

# Copy application source (no package.json needed - stdlib only, no npm install)
COPY server.js .

# Document the port the app listens on (informational; does not publish it)
EXPOSE 3000

# Default command that starts the server when the container runs
CMD ["node", "server.js"]
