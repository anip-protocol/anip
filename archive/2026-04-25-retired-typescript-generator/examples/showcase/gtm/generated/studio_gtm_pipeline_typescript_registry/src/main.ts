import { serve } from "@hono/node-server";
import { app, stop } from "./app.js";

const defaultPort = 4100;
const port = Number(process.env.PORT || defaultPort);
const label = "GTM Pipeline Q2 Review";

const server = serve({ fetch: app.fetch, port }, (info) => {
  console.log(`${label} running on http://localhost:${info.port}`);
});

process.on("SIGINT", () => {
  stop();
  server.close();
});
