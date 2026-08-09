import fs from "node:fs/promises";
import http from "node:http";
import path from "node:path";
import chokidar from "chokidar";
import { WebSocketServer } from "ws";
import { buildSite } from "./build.js";
import type { BuildOptions } from "./types.js";

const MIME: Record<string, string> = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json",
  ".xml": "application/xml",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".gif": "image/gif",
  ".ico": "image/x-icon",
  ".txt": "text/plain; charset=utf-8",
};

export function reloadScript(port: number): string {
  return `<script>
(function () {
  var ws = new WebSocket("ws://" + location.hostname + ":${port}");
  ws.onmessage = function (e) { if (e.data === "reload") location.reload(); };
  ws.onclose = function () { setTimeout(function () { location.reload(); }, 1000); };
})();
</script>`;
}

export interface DevServer {
  port: number;
  close(): Promise<void>;
}

export interface ServeOptions extends BuildOptions {
  port?: number;
}

/** Resolve a URL path to a file inside root, guarding against traversal. */
export function resolveStatic(root: string, urlPath: string): string | null {
  const decoded = decodeURIComponent(urlPath.split("?")[0] ?? "/");
  let rel = path.posix.normalize(decoded).replace(/^\/+/, "");
  if (rel === "" || decoded.endsWith("/")) rel = path.posix.join(rel, "index.html");
  const full = path.resolve(root, rel);
  if (!full.startsWith(path.resolve(root) + path.sep) && full !== path.resolve(root)) return null;
  return full;
}

/** Start dev server: initial build, static serving, rebuild + WS reload on change. */
export async function serve(options: ServeOptions): Promise<DevServer> {
  const port = options.port ?? 3000;
  const buildOpts: BuildOptions = { ...options, injectScript: reloadScript(port) };

  await buildSite(buildOpts);

  const server = http.createServer(async (req, res) => {
    const file = resolveStatic(options.outputDir, req.url ?? "/");
    if (!file) {
      res.writeHead(403).end("Forbidden");
      return;
    }
    try {
      let target = file;
      const stat = await fs.stat(target).catch(() => null);
      if (stat?.isDirectory()) target = path.join(target, "index.html");
      const body = await fs.readFile(target);
      res.writeHead(200, { "content-type": MIME[path.extname(target)] ?? "application/octet-stream" });
      res.end(body);
    } catch {
      res.writeHead(404, { "content-type": "text/html; charset=utf-8" });
      res.end(`<h1>404 Not Found</h1>${reloadScript(port)}`);
    }
  });

  const wss = new WebSocketServer({ server });

  let building = false;
  let pending = false;
  const rebuild = async () => {
    if (building) {
      pending = true;
      return;
    }
    building = true;
    try {
      await buildSite(buildOpts);
      for (const client of wss.clients) client.send("reload");
      console.log("[ssg] rebuilt, reload sent");
    } catch (err) {
      console.error("[ssg] rebuild failed:", err);
    } finally {
      building = false;
      if (pending) {
        pending = false;
        void rebuild();
      }
    }
  };

  const watcher = chokidar.watch([options.sourceDir, options.templateDir], {
    ignoreInitial: true,
  });
  watcher.on("all", () => void rebuild());

  await new Promise<void>((resolve) => server.listen(port, resolve));
  console.log(`[ssg] serving ${options.outputDir} at http://localhost:${port}`);

  return {
    port,
    async close() {
      await watcher.close();
      wss.close();
      await new Promise<void>((resolve, reject) =>
        server.close((err) => (err ? reject(err) : resolve())),
      );
    },
  };
}
