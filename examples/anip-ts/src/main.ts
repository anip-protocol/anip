import { serve } from "@hono/node-server";
import { app, stop } from "./app.js";

const server = serve({ fetch: app.fetch, port: 4100 }, (info) => {
  console.log(`ANIP Flight Service running on http://localhost:${info.port}`);
});

process.on("SIGINT", () => {
  stop();
  server.close();
});
