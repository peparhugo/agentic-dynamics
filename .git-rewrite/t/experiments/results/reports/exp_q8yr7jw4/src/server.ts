import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import chokidar from "chokidar";
import { WebSocketServer, WebSocket } from "ws";
import { buildSite } from "./build.js";
import type { SiteConfig } from "./types.js";

const MIME: Record<string, string> = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css",
  ".js": "text/javascript",
  ".json": "application/json",
  ".xml": "application/xml",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".gif": "image/gif",
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

/** Inject the live-reload script into an HTML document (before </body> if present). */
export function injectReloadScript(html: string): string {
  if (/<\/body>/i.test(html)) return html.replace(/<\/body>/i, `${RELOAD_SCRIPT}\n</body>`);
  return html + RELOAD_SCRIPT;
}

/** Resolve a request URL to a file inside outDir, guarding against path traversal. */
export function resolveRequestPath(outDir: string, urlPath: string): string | null {
  const decoded = decodeURIComponent(urlPath.split("?")[0] ?? "/");
  const safe = path.normalize(decoded).replace(/^(\.\.[/\\])+/, "");
  let full = path.join(outDir, safe);
  if (!full.startsWith(path.resolve(outDir))) return null;
  if (fs.existsSync(full) && fs.statSync(full).isDirectory()) full = path.join(full, "index.html");
  return fs.existsSync(full) && fs.statSync(full).isFile() ? full : null;
}

export interface DevServer {
  close(): Promise<void>;
  port: number;
}

/** Start the dev server: static file serving + rebuild-on-change + WebSocket live reload. */
export async function serve(site: SiteConfig, port: number): Promise<DevServer> {
  buildSite(site);

  const server = http.createServer((req, res) => {
    const file = resolveRequestPath(path.resolve(site.outDir), req.url ?? "/");
    if (!file) {
      res.writeHead(404, { "Content-Type": "text/plain" });
      res.end("404 Not Found");
      return;
    }
    const ext = path.extname(file);
    const type = MIME[ext] ?? "application/octet-stream";
    let body: Buffer | string = fs.readFileSync(file);
    if (ext === ".html") body = injectReloadScript(body.toString("utf8"));
    res.writeHead(200, { "Content-Type": type });
    res.end(body);
  });

  const wss = new WebSocketServer({ server, path: "/__livereload" });
  const broadcast = (msg: string) => {
    for (const client of wss.clients) {
      if (client.readyState === WebSocket.OPEN) client.send(msg);
    }
  };

  const watcher = chokidar.watch([site.sourceDir, site.templateDir], {
    ignoreInitial: true,
    awaitWriteFinish: { stabilityThreshold: 100, pollInterval: 20 },
  });

  let rebuildTimer: NodeJS.Timeout | undefined;
  watcher.on("all", (event, file) => {
    clearTimeout(rebuildTimer);
    rebuildTimer = setTimeout(() => {
      try {
        console.log(`[ssg] ${event}: ${file} — rebuilding`);
        buildSite(site);
        broadcast("reload");
      } catch (err) {
        console.error(`[ssg] rebuild failed:`, err instanceof Error ? err.message : err);
      }
    }, 50);
  });

  await new Promise<void>((resolve) => server.listen(port, resolve));
  const actualPort = (server.address() as { port: number }).port;
  console.log(`[ssg] serving ${site.outDir} at http://localhost:${actualPort} (live reload enabled)`);

  return {
    port: actualPort,
    close: async () => {
      clearTimeout(rebuildTimer);
      await watcher.close();
      wss.close();
      await new Promise<void>((resolve, reject) => server.close((e) => (e ? reject(e) : resolve())));
    },
  };
}
