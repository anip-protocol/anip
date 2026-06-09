import { serve } from "@hono/node-server";
import { app, stop } from "./app.js";

const defaultPort = 9163;
const port = Number(process.env.PORT || defaultPort);
const label = "Notion Fronting Showcase 0.2.0";

const server = serve({ fetch: app.fetch, port }, (info) => {
  console.log(`${label} running on http://localhost:${info.port}`);
});

process.on("SIGINT", () => {
  stop();
  server.close();
});
