import http from "node:http";
import fs from "node:fs";
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
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
  ".txt": "text/plain; charset=utf-8",
};

export const RELOAD_SNIPPET = `<script>
(() => {
  const ws = new WebSocket("ws://" + location.host + "/__livereload");
  ws.onmessage = (e) => { if (e.data === "reload") location.reload(); };
  ws.onclose = () => setTimeout(() => location.reload(), 1000);
})();
</script>`;

/** Inject the live-reload script before </body> (or append if absent). */
export function injectReloadScript(html: string): string {
  const i = html.lastIndexOf("</body>");
  if (i === -1) return html + RELOAD_SNIPPET;
  return html.slice(0, i) + RELOAD_SNIPPET + html.slice(i);
}

export interface DevServer {
  close(): Promise<void>;
  port: number;
}

export async function startDevServer(config: SiteConfig, port: number): Promise<DevServer> {
  buildSite(config); // initial build

  const server = http.createServer((req, res) => {
    const urlPath = decodeURIComponent((req.url ?? "/").split("?")[0]);
    let rel = urlPath.endsWith("/") ? urlPath + "index.html" : urlPath;
    let abs = path.join(config.outDir, path.normalize(rel));
    if (!abs.startsWith(path.resolve(config.outDir)) && !abs.startsWith(config.outDir)) {
      res.writeHead(403).end("Forbidden");
      return;
    }
    if (!fs.existsSync(abs) && fs.existsSync(abs + ".html")) abs += ".html";
    if (!fs.existsSync(abs) || fs.statSync(abs).isDirectory()) {
      res.writeHead(404, { "Content-Type": "text/html" }).end(injectReloadScript("<h1>404</h1>"));
      return;
    }
    const ext = path.extname(abs).toLowerCase();
    const type = MIME[ext] ?? "application/octet-stream";
    let body: Buffer | string = fs.readFileSync(abs);
    if (ext === ".html") body = injectReloadScript(body.toString("utf8"));
    res.writeHead(200, { "Content-Type": type }).end(body);
  });

  const wss = new WebSocketServer({ server, path: "/__livereload" });
  const broadcast = () => {
    for (const c of wss.clients) if (c.readyState === WebSocket.OPEN) c.send("reload");
  };

  // Debounced rebuild-on-change. Latency-first: cheap sites rebuild in ms;
  // debounce collapses editor save bursts into one rebuild.
  let timer: NodeJS.Timeout | null = null;
  const scheduleRebuild = (file: string) => {
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => {
      const t0 = Date.now();
      try {
        buildSite(config);
        console.log(`[ssgen] rebuilt in ${Date.now() - t0}ms (${file})`);
        broadcast();
      } catch (err) {
        console.error("[ssgen] rebuild failed:", err);
      }
    }, 50);
  };

  const watcher = chokidar.watch([config.sourceDir, config.templateDir], {
    ignoreInitial: true,
  });
  watcher.on("all", (_evt, file) => scheduleRebuild(file));

  await new Promise<void>((resolve) => server.listen(port, resolve));
  const actualPort = (server.address() as { port: number }).port;
  console.log(`[ssgen] dev server: http://localhost:${actualPort}`);

  return {
    port: actualPort,
    async close() {
      await watcher.close();
      wss.close();
      await new Promise<void>((resolve, reject) =>
        server.close((e) => (e ? reject(e) : resolve()))
      );
    },
  };
}
