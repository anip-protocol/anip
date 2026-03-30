/**
 * ANIP Studio — mount the inspection and invocation UI at /studio.
 *
 * Works with any framework that supports Hono-style routing.
 * For Express/Fastify, use the appropriate framework helper to serve static files.
 */
import { readFileSync, existsSync, statSync } from "fs";
import { join, resolve } from "path";

const STATIC_DIR = resolve(__dirname, "..", "static");

/** Minimal interface for the service — avoids cross-module import issues. */
export interface StudioService {
  serviceId: string;
}

/**
 * Mount ANIP Studio on a Hono app.
 *
 * @param app - Hono app instance
 * @param service - ANIPService (or any object with serviceId)
 * @param prefix - URL prefix (default: "/studio")
 */
export function mountAnipStudio(
  app: { get: Function; use?: Function },
  service: StudioService,
  prefix: string = "/studio",
): void {
  if (!existsSync(STATIC_DIR)) {
    console.warn(
      "ANIP Studio static assets not found. " +
        "Run 'cd studio && npm run build' and sync assets.",
    );
    return;
  }

  const indexHtml = readFileSync(join(STATIC_DIR, "index.html"), "utf-8");

  // Config endpoint
  app.get(`${prefix}/config.json`, (c: any) => {
    return c.json({ service_id: service.serviceId, embedded: true });
  });

  // Static assets
  app.get(`${prefix}/assets/:file`, (c: any) => {
    const filePath = join(STATIC_DIR, "assets", c.req.param("file"));
    if (existsSync(filePath) && statSync(filePath).isFile()) {
      const ext = filePath.split(".").pop() || "";
      const types: Record<string, string> = {
        js: "application/javascript",
        css: "text/css",
        json: "application/json",
        png: "image/png",
        svg: "image/svg+xml",
      };
      return new Response(readFileSync(filePath), {
        headers: {
          "Content-Type": types[ext] || "application/octet-stream",
          "Cache-Control": "public, max-age=31536000, immutable",
        },
      });
    }
    return c.notFound();
  });

  // SPA fallback
  app.get(`${prefix}`, (c: any) =>
    c.html(indexHtml),
  );
  app.get(`${prefix}/`, (c: any) =>
    c.html(indexHtml),
  );
  app.get(`${prefix}/*`, (c: any) => {
    const path = c.req.path.replace(prefix, "");
    const filePath = join(STATIC_DIR, path);
    if (existsSync(filePath) && statSync(filePath).isFile()) {
      return new Response(readFileSync(filePath));
    }
    return c.html(indexHtml);
  });
}
