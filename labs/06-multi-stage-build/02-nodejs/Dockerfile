FROM node:24-alpine AS deps
WORKDIR /deps
COPY package.json ./
RUN npm install --omit=dev

FROM node:24-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production
COPY --from=deps /deps/node_modules ./node_modules
COPY app.js package.json ./
EXPOSE 8080
CMD ["node", "app.js"]
