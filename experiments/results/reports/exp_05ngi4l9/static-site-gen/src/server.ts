import http from "node:http";
import fs from "node:fs/promises";
import path from "node:path";
import { WebSocketServer, WebSocket } from "ws";
import chokidar from "chokidar";
import type { ServerOptions } from "./types.js";
import { build } from "./build.js";
import type { BuildOptions } from "./types.js";

export function startDevServer(serverOptions: ServerOptions, buildOptions: BuildOptions): void {
  let clients: WebSocket[] = [];

  const server = http.createServer(async (req, res) => {
    const url = req.url === "/" ? "/index.html" : req.url ?? "/index.html";
    const filePath = path.join(buildOptions.output, url);

    try {
      const content = await fs.readFile(filePath);
      const ext = path.extname(filePath);
      const mime: Record<string, string> = {
        ".html": "text/html",
        ".css": "text/css",
        ".js": "application/javascript",
        ".xml": "application/xml",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".svg": "image/svg+xml",
      };
      res.writeHead(200, { "Content-Type": mime[ext] ?? "text/plain" });
      res.end(content);
    } catch {
      res.writeHead(404);
      res.end("Not Found");
    }
  });

  const wss = new WebSocketServer({ server });

  wss.on("connection", (ws) => {
    clients.push(ws);
    ws.on("close", () => {
      clients = clients.filter((c) => c !== ws);
    });
  });

  const watcher = chokidar.watch(
    [buildOptions.source, buildOptions.templates],
    { ignoreInitial: true }
  );

  const debouncedRebuild = debounce(async () => {
    try {
      await build(buildOptions);
      const data = JSON.stringify({ type: "reload" });
      for (const client of clients) {
        if (client.readyState === WebSocket.OPEN) {
          client.send(data);
        }
      }
      console.log("Rebuilt and signaled reload");
    } catch (err) {
      console.error("Build error:", err);
    }
  }, 300);

  watcher.on("all", () => {
    debouncedRebuild();
  });

  server.listen(serverOptions.port, () => {
    console.log(`Dev server running at http://localhost:${serverOptions.port}`);
  });
}

function debounce(fn: () => void, ms: number): () => void {
  let timer: ReturnType<typeof setTimeout> | null = null;
  return () => {
    if (timer) clearTimeout(timer);
    timer = setTimeout(fn, ms);
  };
}
