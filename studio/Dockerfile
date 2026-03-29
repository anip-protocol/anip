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

# Remove default config
RUN rm /etc/nginx/conf.d/default.conf

# Copy app files
COPY --from=build /app/dist/ /usr/share/nginx/html/
COPY nginx.conf /etc/nginx/nginx.conf
COPY standalone-config.json /usr/share/nginx/html/config.json

# Make html directory readable by non-root
RUN chmod -R 755 /usr/share/nginx/html

# Run as non-root user
RUN addgroup -g 1001 -S anip && adduser -u 1001 -S anip -G anip
USER 1001

# Read-only filesystem — only /tmp is writable (for nginx pid + temp files)
VOLUME ["/tmp"]

EXPOSE 8080
