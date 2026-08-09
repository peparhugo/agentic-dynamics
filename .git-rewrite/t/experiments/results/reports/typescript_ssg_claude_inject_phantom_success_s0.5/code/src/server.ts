import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import chokidar from "chokidar";
import { WebSocketServer } from "ws";
import { buildSite } from "./build.js";
import type { SiteConfig } from "./types.js";

const MIME: Record<string, string> = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json",
  ".xml": "application/xml; charset=utf-8",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".gif": "image/gif",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
  ".txt": "text/plain; charset=utf-8",
  ".woff2": "font/woff2",
};

export const RELOAD_SCRIPT = `<script>
(() => {
  const ws = new WebSocket("ws://" + location.host + "/__livereload");
  ws.onmessage = (e) => { if (e.data === "reload") location.reload(); };
  ws.onclose = () => setTimeout(() => location.reload(), 1000);
})();
</script>`;

/** Inject the live-reload script before </body> (or append if absent). */
export function injectReloadScript(html: string): string {
  if (html.includes("</body>")) return html.replace("</body>", `${RELOAD_SCRIPT}\n</body>`);
  return html + RELOAD_SCRIPT;
}

export interface DevServer {
  close(): Promise<void>;
  port: number;
}

/**
 * Serve the output directory with live reload. Watches source + template dirs
 * with chokidar, rebuilds on change, and broadcasts "reload" over WebSocket.
 */
export async function startDevServer(config: SiteConfig, port: number): Promise<DevServer> {
  buildSite(config);

  const server = http.createServer((req, res) => {
    const urlPath = decodeURIComponent((req.url ?? "/").split("?")[0]);
    let filePath = path.join(config.outDir, path.normalize(urlPath).replace(/^(\.\.[/\\])+/, ""));
    if (!filePath.startsWith(path.resolve(config.outDir)) && !filePath.startsWith(config.outDir)) {
      res.writeHead(403).end("Forbidden");
      return;
    }
    if (fs.existsSync(filePath) && fs.statSync(filePath).isDirectory()) {
      filePath = path.join(filePath, "index.html");
    }
    if (!fs.existsSync(filePath)) {
      res.writeHead(404, { "Content-Type": "text/html" });
      res.end(injectReloadScript("<h1>404 Not Found</h1>"));
      return;
    }
    const ext = path.extname(filePath);
    const type = MIME[ext] ?? "application/octet-stream";
    let content: Buffer | string = fs.readFileSync(filePath);
    if (ext === ".html") content = injectReloadScript(content.toString("utf8"));
    res.writeHead(200, { "Content-Type": type });
    res.end(content);
  });

  const wss = new WebSocketServer({ server, path: "/__livereload" });
  const broadcast = () => {
    for (const client of wss.clients) {
      if (client.readyState === 1) client.send("reload");
    }
  };

  const watcher = chokidar.watch([config.sourceDir, config.templateDir], {
    ignoreInitial: true,
    awaitWriteFinish: { stabilityThreshold: 100, pollInterval: 20 },
  });
  let timer: ReturnType<typeof setTimeout> | null = null;
  watcher.on("all", (event, file) => {
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => {
      try {
        console.log(`[ssg] ${event}: ${file} — rebuilding`);
        buildSite(config);
        broadcast();
      } catch (err) {
        console.error("[ssg] rebuild failed:", err);
      }
    }, 50);
  });

  await new Promise<void>((resolve) => server.listen(port, resolve));
  const actualPort = (server.address() as { port: number }).port;
  console.log(`[ssg] dev server: http://localhost:${actualPort}`);

  return {
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
