import { createServer, IncomingMessage, ServerResponse } from "node:http";
import { readFile, stat } from "node:fs/promises";
import { join, extname } from "node:path";
import { WebSocketServer, WebSocket } from "ws";
import { watch } from "chokidar";
import { buildSite } from "./build.js";
import type { SiteConfig } from "./types.js";

const MIME_TYPES: Record<string, string> = {
  ".html": "text/html",
  ".css": "text/css",
  ".js": "application/javascript",
  ".json": "application/json",
  ".xml": "application/xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
  ".woff2": "font/woff2",
};

let sockets = new Set<WebSocket>();

export async function startServer(
  outDir: string,
  srcDir: string,
  templateDir: string,
  config: SiteConfig,
  port: number,
): Promise<void> {
  const wss = new WebSocketServer({ port: 35729 });

  wss.on("connection", (ws) => {
    sockets.add(ws);
    ws.on("close", () => sockets.delete(ws));
  });

  function reload() {
    for (const ws of sockets) {
      ws.send("reload");
    }
  }

  const server = createServer(async (req: IncomingMessage, res: ServerResponse) => {
    let urlPath = req.url ?? "/";
    if (urlPath === "/") urlPath = "/index.html";

    const filePath = join(outDir, urlPath);
    try {
      await stat(filePath);
      const ext = extname(filePath).toLowerCase();
      const mime = MIME_TYPES[ext] ?? "application/octet-stream";
      const content = await readFile(filePath);
      res.writeHead(200, { "Content-Type": mime });
      res.end(content);
    } catch {
      try {
        const notFoundPath = join(outDir, "404", "index.html");
        const content = await readFile(notFoundPath);
        res.writeHead(404, { "Content-Type": "text/html" });
        res.end(content);
      } catch {
        res.writeHead(404, { "Content-Type": "text/plain" });
        res.end("404 Not Found");
      }
    }
  });

  const watcher = watch([srcDir, templateDir], {
    ignoreInitial: true,
    awaitWriteFinish: { stabilityThreshold: 200, pollInterval: 50 },
  });

  let rebuildTimeout: ReturnType<typeof setTimeout> | null = null;

  watcher.on("all", async (_event, _path) => {
    if (rebuildTimeout) clearTimeout(rebuildTimeout);
    rebuildTimeout = setTimeout(async () => {
      try {
        await buildSite(srcDir, templateDir, outDir, config, true);
        reload();
        console.log("[ssg] Rebuilt site");
      } catch (err) {
        console.error("[ssg] Build error:", err);
      }
    }, 300);
  });

  server.listen(port, () => {
    console.log(`[ssg] Dev server running at http://localhost:${port}`);
  });
}
