# ---- Stage 1: build the React app with Node ----
FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies first so this layer is cached unless package.json changes
COPY package.json ./
RUN npm install

# Copy the source and produce the optimised static bundle in /app/dist
COPY index.html vite.config.js ./
COPY src/ ./src/
RUN npm run build

# ---- Stage 2: serve the built static files with Nginx ----
FROM nginx:alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf

# Only the compiled bundle is copied - Node, npm and node_modules are left behind
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80
