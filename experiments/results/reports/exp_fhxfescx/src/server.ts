import { createServer, type Server } from "node:http";
import { promises as fs } from "node:fs";
import path from "node:path";
import chokidar, { type FSWatcher } from "chokidar";
import { WebSocketServer, WebSocket } from "ws";
import { buildSite } from "./build.js";
import type { SiteConfig } from "./types.js";

const MIME: Record<string, string> = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json",
  ".xml": "application/xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".gif": "image/gif",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
  ".txt": "text/plain; charset=utf-8",
};

export const RELOAD_SCRIPT = `<script>
(() => {
  const ws = new WebSocket("ws://" + location.host + "/__livereload");
  ws.onmessage = (e) => { if (e.data === "reload") location.reload(); };
  ws.onclose = () => setTimeout(() => location.reload(), 1000);
})();
</script>`;

/** Inject the live-reload script before </body>, or append if absent. */
export function injectReloadScript(html: string): string {
  const idx = html.lastIndexOf("</body>");
  if (idx === -1) return html + RELOAD_SCRIPT;
  return html.slice(0, idx) + RELOAD_SCRIPT + html.slice(idx);
}

export interface DevServer {
  server: Server;
  close(): Promise<void>;
  port: number;
}

export async function startDevServer(config: SiteConfig, port: number): Promise<DevServer> {
  await buildSite(config);

  const server = createServer(async (req, res) => {
    try {
      const urlPath = decodeURIComponent((req.url ?? "/").split("?")[0]);
      let relPath = urlPath.endsWith("/") ? urlPath + "index.html" : urlPath;
      relPath = path.normalize(relPath).replace(/^([/\\]|\.\.)+/, "");
      const filePath = path.join(config.outputDir, relPath);
      if (!path.resolve(filePath).startsWith(path.resolve(config.outputDir))) {
        res.writeHead(403);
        res.end("Forbidden");
        return;
      }
      let data: Buffer;
      try {
        data = await fs.readFile(filePath);
      } catch {
        res.writeHead(404, { "Content-Type": "text/html; charset=utf-8" });
        res.end(injectReloadScript("<h1>404 Not Found</h1>"));
        return;
      }
      const ext = path.extname(filePath).toLowerCase();
      const mime = MIME[ext] ?? "application/octet-stream";
      if (ext === ".html") {
        res.writeHead(200, { "Content-Type": mime });
        res.end(injectReloadScript(data.toString("utf8")));
      } else {
        res.writeHead(200, { "Content-Type": mime });
        res.end(data);
      }
    } catch (err) {
      res.writeHead(500);
      res.end(String(err));
    }
  });

  const wss = new WebSocketServer({ server, path: "/__livereload" });
  const broadcast = () => {
    for (const client of wss.clients) {
      if (client.readyState === WebSocket.OPEN) client.send("reload");
    }
  };

  let rebuilding = false;
  let pending = false;
  const rebuild = async () => {
    if (rebuilding) {
      pending = true;
      return;
    }
    rebuilding = true;
    try {
      await buildSite(config);
      broadcast();
      console.log("[ssg] rebuilt, reload sent");
    } catch (err) {
      console.error("[ssg] rebuild failed:", err);
    } finally {
      rebuilding = false;
      if (pending) {
        pending = false;
        void rebuild();
      }
    }
  };

  const watcher: FSWatcher = chokidar.watch([config.sourceDir, config.templateDir], {
    ignoreInitial: true,
    awaitWriteFinish: { stabilityThreshold: 50, pollInterval: 10 },
  });
  watcher.on("all", () => void rebuild());

  await new Promise<void>((resolve) => server.listen(port, resolve));
  const actualPort = (server.address() as { port: number }).port;
  console.log(`[ssg] dev server at http://localhost:${actualPort}`);

  return {
    server,
    port: actualPort,
    async close() {
      await watcher.close();
      wss.close();
      await new Promise<void>((resolve, reject) =>
        server.close((err) => (err ? reject(err) : resolve()))
      );
    },
  };
}
