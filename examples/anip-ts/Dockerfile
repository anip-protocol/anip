# Stage 1: Build
FROM node:22-alpine AS builder

WORKDIR /app

COPY package.json ./
RUN npm install

COPY tsconfig.json ./
COPY src/ ./src/

RUN npx tsc

# Stage 2: Run
FROM node:22-alpine

WORKDIR /app

COPY package.json ./
RUN npm install --omit=dev

COPY --from=builder /app/dist/ ./dist/

EXPOSE 8000

CMD ["node", "dist/server.js"]
