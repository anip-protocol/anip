# syntax=docker/dockerfile:1.7

FROM node:22-alpine AS registry-ui
WORKDIR /src/registry

COPY registry/package.json registry/package-lock.json ./
RUN npm ci

COPY registry/ ./
ENV VITE_BASE_PATH=/registry/
RUN npm run build

FROM golang:1.25-alpine AS registry-api
WORKDIR /src/packages/go

COPY packages/go/go.mod packages/go/go.sum ./
RUN go mod download

COPY packages/go/ ./
RUN CGO_ENABLED=0 go build \
  -trimpath \
  -ldflags "-s -w" \
  -o /out/anip-registry \
  ./cmd/anip-registry

FROM alpine:3.22
RUN apk add --no-cache ca-certificates wget \
  && addgroup -S anip \
  && adduser -S -G anip anip

WORKDIR /app
COPY --from=registry-api /out/anip-registry /usr/local/bin/anip-registry
COPY --from=registry-ui /src/registry/dist /app/registry/dist

ENV ANIP_REGISTRY_ADDR=:8200
ENV ANIP_REGISTRY_UI_DIR=/app/registry/dist
ENV ANIP_REGISTRY_MODE=dev

EXPOSE 8200
USER anip

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=6 \
  CMD wget -qO- http://127.0.0.1:8200/registry-api/v1/readyz >/dev/null || exit 1

ENTRYPOINT ["anip-registry"]
