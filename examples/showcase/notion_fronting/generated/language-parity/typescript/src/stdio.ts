import { serveStdio } from "@anip-dev/stdio";
import { service, stop } from "./app.js";

try {
  await serveStdio(service);
} finally {
  stop();
}
