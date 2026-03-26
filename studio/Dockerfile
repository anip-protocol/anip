# --- Build stage ---
FROM node:22-alpine AS build

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

COPY src/ src/
COPY index.html vite.config.ts tsconfig.json tsconfig.app.json tsconfig.node.json ./

ENV VITE_BASE_PATH=/
RUN npx vite build

# --- Serve stage ---
FROM nginx:alpine

COPY --from=build /app/dist/ /usr/share/nginx/html/
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY standalone-config.json /usr/share/nginx/html/config.json

EXPOSE 80
