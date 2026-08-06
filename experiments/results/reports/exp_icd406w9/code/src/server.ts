import http from "node:http";
import { promises as fs } from "node:fs";
import path from "node:path";
import chokidar from "chokidar";
import { WebSocketServer, WebSocket } from "ws";
import { build, type BuildOptions } from "./build.js";

const MIME: Record<string, string> = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json",
  ".xml": "application/xml",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".gif": "image/gif",
  ".ico": "image/x-icon",
  ".txt": "text/plain; charset=utf-8",
  ".woff2": "font/woff2",
};

export function reloadScript(port: number): string {
  return `\n<script>
(() => {
  const connect = () => {
    const ws = new WebSocket("ws://" + location.hostname + ":${port}/__livereload");
    ws.onmessage = (e) => { if (e.data === "reload") location.reload(); };
    ws.onclose = () => setTimeout(connect, 1000);
  };
  connect();
})();
</script>\n`;
}

export interface ServeOptions extends BuildOptions {
  port: number;
}

export interface DevServer {
  close(): Promise<void>;
  port: number;
}

export async function serve(opts: ServeOptions): Promise<DevServer> {
  const buildOpts: BuildOptions = { ...opts, injectHtml: reloadScript(opts.port) };
  await build(buildOpts);

  const server = http.createServer(async (req, res) => {
    try {
      const urlPath = decodeURIComponent((req.url ?? "/").split("?")[0] ?? "/");
      let rel = path.normalize(urlPath).replace(/^([/\\]|\.\.)+/, "");
      let abs = path.join(opts.output, rel);
      const stat = await fs.stat(abs).catch(() => null);
      if (stat?.isDirectory() || urlPath.endsWith("/")) abs = path.join(abs, "index.html");
      const body = await fs.readFile(abs);
      res.writeHead(200, {
        "Content-Type": MIME[path.extname(abs)] ?? "application/octet-stream",
        "Cache-Control": "no-store",
      });
      res.end(body);
    } catch {
      res.writeHead(404, { "Content-Type": "text/plain" });
      res.end("Not Found");
    }
  });

  const wss = new WebSocketServer({ server, path: "/__livereload" });
  const broadcast = (msg: string) => {
    for (const client of wss.clients) {
      if (client.readyState === WebSocket.OPEN) client.send(msg);
    }
  };

  let pending: NodeJS.Timeout | null = null;
  const rebuild = () => {
    if (pending) clearTimeout(pending);
    pending = setTimeout(async () => {
      try {
        await build(buildOpts);
        broadcast("reload");
        console.log("[ssg] rebuilt, reload sent");
      } catch (err) {
        console.error("[ssg] rebuild failed:", err);
      }
    }, 100);
  };

  const watcher = chokidar.watch([opts.source, opts.templates], {
    ignoreInitial: true,
  });
  watcher.on("all", rebuild);

  await new Promise<void>((resolve) => server.listen(opts.port, resolve));
  console.log(`[ssg] dev server at http://localhost:${opts.port}/ (live reload enabled)`);

  return {
    port: opts.port,
    async close() {
      if (pending) clearTimeout(pending);
      await watcher.close();
      for (const client of wss.clients) client.terminate();
      await new Promise<void>((resolve, reject) =>
        server.close((err) => (err ? reject(err) : resolve()))
      );
    },
  };
}
