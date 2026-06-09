import { serve } from "@hono/node-server";
import { app, stop } from "./app.js";

const defaultPort = 4201;
const port = Number(process.env.PORT || defaultPort);
const label = "GTM Operator Contract 20260512235040";

const server = serve({ fetch: app.fetch, port }, (info) => {
  console.log(`${label} running on http://localhost:${info.port}`);
});

process.on("SIGINT", () => {
  stop();
  server.close();
});
