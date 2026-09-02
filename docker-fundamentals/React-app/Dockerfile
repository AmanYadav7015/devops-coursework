# ---- Stage 1: build ----
# Node image used only to install deps and bundle the React app with esbuild.
# This stage (node_modules etc.) is discarded from the final image.
FROM node:22-alpine AS build

WORKDIR /app

# Copy manifest first so npm install is cached unless dependencies change
COPY package.json ./
RUN npm install

# Copy source and public template, then bundle React -> public/bundle.js
COPY src ./src
COPY public ./public
RUN npm run build

# ---- Stage 2: runtime ----
# Tiny nginx image just serves the static build output - no Node.js,
# no node_modules, no npm in the final image.
FROM nginx:alpine

# public/ now contains index.html + the esbuild-generated bundle.js
COPY --from=build /app/public /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
