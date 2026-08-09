import http from "node:http";
import fs from "node:fs/promises";
import path from "node:path";
import chokidar from "chokidar";
import { WebSocketServer, WebSocket } from "ws";
import { buildSite, type BuildOptions } from "./build.js";

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
  ".woff2": "font/woff2",
};

export const RELOAD_SCRIPT = `<script>
(() => {
  const ws = new WebSocket("ws://" + location.host + "/__livereload");
  ws.onmessage = (e) => { if (e.data === "reload") location.reload(); };
  ws.onclose = () => setTimeout(() => location.reload(), 1000);
})();
</script>`;

/** Inject the live-reload script before </body>, or append if no body tag. */
export function injectReloadScript(html: string): string {
  const idx = html.lastIndexOf("</body>");
  if (idx === -1) return html + RELOAD_SCRIPT;
  return html.slice(0, idx) + RELOAD_SCRIPT + html.slice(idx);
}

export interface DevServer {
  server: http.Server;
  port: number;
  close(): Promise<void>;
}

/** Resolve a URL path to a file inside root, guarding against path traversal. */
export async function resolveFile(root: string, urlPath: string): Promise<string | null> {
  const decoded = decodeURIComponent(urlPath.split("?")[0] ?? "/");
  const safe = path.normalize(decoded).replace(/^(\.\.[/\\])+/, "");
  let full = path.join(root, safe);
  if (!full.startsWith(path.resolve(root))) return null;
  try {
    const stat = await fs.stat(full);
    if (stat.isDirectory()) full = path.join(full, "index.html");
    await fs.access(full);
    return full;
  } catch {
    return null;
  }
}

export async function startDevServer(opts: BuildOptions & { port?: number }): Promise<DevServer> {
  const port = opts.port ?? 3000;
  await buildSite(opts);

  const server = http.createServer(async (req, res) => {
    const file = await resolveFile(opts.outDir, req.url ?? "/");
    if (!file) {
      res.writeHead(404, { "content-type": "text/plain" });
      res.end("Not found");
      return;
    }
    const ext = path.extname(file).toLowerCase();
    const mime = MIME[ext] ?? "application/octet-stream";
    let body: Buffer | string = await fs.readFile(file);
    if (ext === ".html") body = injectReloadScript(body.toString("utf8"));
    res.writeHead(200, { "content-type": mime });
    res.end(body);
  });

  const wss = new WebSocketServer({ server, path: "/__livereload" });
  const broadcast = (msg: string) => {
    for (const client of wss.clients) {
      if (client.readyState === WebSocket.OPEN) client.send(msg);
    }
  };

  let timer: NodeJS.Timeout | undefined;
  const watcher = chokidar.watch([opts.sourceDir, opts.templateDir], {
    ignoreInitial: true,
  });
  watcher.on("all", () => {
    // Debounce bursts of file events into a single rebuild.
    clearTimeout(timer);
    timer = setTimeout(async () => {
      try {
        await buildSite(opts);
        broadcast("reload");
        console.log("[ssg] rebuilt, reload sent");
      } catch (err) {
        console.error("[ssg] rebuild failed:", err);
      }
    }, 100);
  });

  await new Promise<void>((resolve) => server.listen(port, resolve));
  const actualPort = (server.address() as { port: number }).port;
  console.log(`[ssg] dev server at http://localhost:${actualPort}/`);

  return {
    server,
    port: actualPort,
    async close() {
      clearTimeout(timer);
      await watcher.close();
      wss.close();
      await new Promise<void>((resolve, reject) =>
        server.close((err) => (err ? reject(err) : resolve())),
      );
    },
  };
}
