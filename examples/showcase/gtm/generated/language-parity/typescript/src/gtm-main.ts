import { serve } from "@hono/node-server";
import { app, stop } from "./gtm-app.js";

const port = Number(process.env.PORT || 4100);
const server = serve({ fetch: app.fetch, port }, (info) => {
  console.log(`GTM TypeScript native service running on http://localhost:${info.port}`);
});

process.on("SIGINT", () => {
  stop();
  server.close();
});

process.on("SIGTERM", () => {
  stop();
  server.close();
});
