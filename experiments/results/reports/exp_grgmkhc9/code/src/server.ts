import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { WebSocketServer, WebSocket } from "ws";
import chokidar from "chokidar";
import { SiteConfig } from "./types";
import { build } from "./build";

export function startDevServer(config: SiteConfig): void {
  const server = http.createServer((req, res) => {
    const url = req.url ?? "/";
    const filePath = url === "/"
      ? path.join(config.outputDir, "index.html")
      : path.join(config.outputDir, url);

    const ext = path.extname(filePath).toLowerCase();
    const mimeTypes: Record<string, string> = {
      ".html": "text/html",
      ".css": "text/css",
      ".js": "application/javascript",
      ".json": "application/json",
      ".png": "image/png",
      ".jpg": "image/jpeg",
      ".svg": "image/svg+xml",
      ".xml": "application/xml",
      ".ico": "image/x-icon",
    };
    const contentType = mimeTypes[ext] ?? "application/octet-stream";

    try {
      const content = fs.readFileSync(filePath);
      res.writeHead(200, { "Content-Type": contentType });
      res.end(content);
    } catch {
      if (!url.includes(".")) {
        try {
          const indexPath = path.join(filePath, "index.html");
          const content = fs.readFileSync(indexPath);
          res.writeHead(200, { "Content-Type": "text/html" });
          res.end(content);
        } catch {
          res.writeHead(404);
          res.end("Not found");
        }
      } else {
        res.writeHead(404);
        res.end("Not found");
      }
    }
  });

  const wss = new WebSocketServer({ server });

  wss.on("connection", (ws: WebSocket) => {
    ws.on("error", () => {});
  });

  function sendReload() {
    for (const client of wss.clients) {
      if (client.readyState === WebSocket.OPEN) {
        client.send("reload");
      }
    }
  }

  let building = false;
  let pendingRebuild = false;

  async function doRebuild() {
    if (building) {
      pendingRebuild = true;
      return;
    }
    building = true;
    pendingRebuild = false;
    try {
      await build(config, true);
      console.log("[statico] Rebuilt at", new Date().toLocaleTimeString());
      sendReload();
    } catch (err) {
      console.error("[statico] Build error:", err);
    } finally {
      building = false;
      if (pendingRebuild) {
        doRebuild();
      }
    }
  }

  const watcher = chokidar.watch([config.sourceDir, config.templateDir], {
    ignoreInitial: true,
    ignorePermissionErrors: true,
  });

  watcher.on("all", (_event: string, _filePath: string) => {
    doRebuild();
  });

  server.listen(config.port, () => {
    console.log(`[statico] Dev server running at http://localhost:${config.port}`);
    console.log(`[statico] Watching ${config.sourceDir} and ${config.templateDir}`);
  });

  process.on("SIGINT", () => {
    watcher.close();
    wss.close();
    server.close();
    process.exit(0);
  });
}
