FROM node:22-slim

WORKDIR /repo

COPY packages/typescript /repo/packages/typescript
COPY examples/showcase/gtm/generated/language-parity/typescript /repo/examples/showcase/gtm/generated/language-parity/typescript

WORKDIR /repo/packages/typescript

RUN npm install \
    && npm --workspace @anip-dev/core run build \
    && npm --workspace @anip-dev/crypto run build \
    && npm --workspace @anip-dev/server run build \
    && npm --workspace @anip-dev/service run build \
    && npm --workspace @anip-dev/hono run build

WORKDIR /repo/examples/showcase/gtm/generated/language-parity/typescript

RUN npm install && npm run build

EXPOSE 4100

CMD ["node", "dist/main.js"]
