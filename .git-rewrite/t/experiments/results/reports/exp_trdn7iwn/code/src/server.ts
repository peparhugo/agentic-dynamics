import http from "node:http";
import { promises as fs } from "node:fs";
import path from "node:path";
import chokidar from "chokidar";
import { WebSocketServer, WebSocket } from "ws";
import { build, type BuildOptions } from "./build.js";

export const LIVE_RELOAD_SNIPPET = `<script>
(() => {
  const connect = () => {
    const ws = new WebSocket("ws://" + location.host + "/__livereload");
    ws.onmessage = (e) => { if (e.data === "reload") location.reload(); };
    ws.onclose = () => setTimeout(connect, 1000);
  };
  connect();
})();
</script>`;

const MIME: Record<string, string> = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json",
  ".xml": "application/xml; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".gif": "image/gif",
  ".ico": "image/x-icon",
  ".txt": "text/plain; charset=utf-8",
  ".woff2": "font/woff2",
};

export interface DevServer {
  port: number;
  close(): Promise<void>;
}

/**
 * Serve `outputDir` over HTTP, rebuild on changes to source/template dirs
 * (via chokidar), and notify browsers over WebSocket to reload.
 */
export async function serve(
  opts: BuildOptions & { port?: number }
): Promise<DevServer> {
  const buildOpts: BuildOptions = { ...opts, injectHtml: LIVE_RELOAD_SNIPPET };
  await build(buildOpts);

  const server = http.createServer(async (req, res) => {
    try {
      const urlPath = decodeURIComponent((req.url ?? "/").split("?")[0] ?? "/");
      const filePath = resolveFile(opts.outputDir, urlPath);
      if (!filePath) {
        res.writeHead(403).end("Forbidden");
        return;
      }
      const content = await readWithIndexFallback(filePath);
      if (content === null) {
        res.writeHead(404, { "Content-Type": "text/html; charset=utf-8" });
        res.end(`<h1>404 Not Found</h1>${LIVE_RELOAD_SNIPPET}`);
        return;
      }
      res.writeHead(200, {
        "Content-Type": MIME[path.extname(content.path).toLowerCase()] ?? "application/octet-stream",
        "Cache-Control": "no-store",
      });
      res.end(content.data);
    } catch (err) {
      res.writeHead(500).end(String(err));
    }
  });

  const wss = new WebSocketServer({ noServer: true });
  server.on("upgrade", (req, socket, head) => {
    if (req.url === "/__livereload") {
      wss.handleUpgrade(req, socket, head, (ws) => wss.emit("connection", ws, req));
    } else {
      socket.destroy();
    }
  });

  const broadcast = (msg: string) => {
    for (const client of wss.clients) {
      if (client.readyState === WebSocket.OPEN) client.send(msg);
    }
  };

  let pending: NodeJS.Timeout | null = null;
  const watcher = chokidar.watch([opts.sourceDir, opts.templateDir], {
    ignoreInitial: true,
  });
  watcher.on("all", () => {
    if (pending) clearTimeout(pending);
    pending = setTimeout(async () => {
      try {
        await build(buildOpts);
        broadcast("reload");
        console.log("[sitegen] rebuilt, reload sent");
      } catch (err) {
        console.error("[sitegen] rebuild failed:", err);
      }
    }, 100);
  });

  const port = await listen(server, opts.port ?? 3000);
  console.log(`[sitegen] dev server at http://localhost:${port}`);

  return {
    port,
    async close() {
      if (pending) clearTimeout(pending);
      await watcher.close();
      for (const client of wss.clients) client.terminate();
      wss.close();
      await new Promise<void>((resolve, reject) =>
        server.close((err) => (err ? reject(err) : resolve()))
      );
    },
  };
}

function resolveFile(root: string, urlPath: string): string | null {
  const resolved = path.resolve(root, "." + path.posix.normalize("/" + urlPath));
  return resolved.startsWith(path.resolve(root)) ? resolved : null;
}

async function readWithIndexFallback(
  filePath: string
): Promise<{ data: Buffer; path: string } | null> {
  const candidates = [filePath, path.join(filePath, "index.html")];
  for (const candidate of candidates) {
    try {
      const stat = await fs.stat(candidate);
      if (stat.isFile()) return { data: await fs.readFile(candidate), path: candidate };
    } catch {
      /* try next */
    }
  }
  return null;
}

function listen(server: http.Server, port: number): Promise<number> {
  return new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(port, () => {
      const addr = server.address();
      resolve(typeof addr === "object" && addr ? addr.port : port);
    });
  });
}
