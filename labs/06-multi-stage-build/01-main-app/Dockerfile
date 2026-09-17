FROM node:24-alpine AS builder
WORKDIR /build
COPY package.json ./
RUN npm install --omit=dev
COPY server.js ./

FROM node:24-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /build/node_modules ./node_modules
COPY --from=builder /build/package.json ./package.json
COPY --from=builder /build/server.js ./server.js
EXPOSE 8080
CMD ["node", "server.js"]
