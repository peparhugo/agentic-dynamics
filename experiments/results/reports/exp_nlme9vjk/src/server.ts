import { createServer, IncomingMessage, ServerResponse } from "node:http";
import { readFileSync, existsSync, statSync } from "node:fs";
import { join, extname } from "node:path";
import { WebSocketServer, WebSocket } from "ws";
import type { SiteConfig } from "./types.js";

const RELOAD_SCRIPT = `<script>(function(){var s=new WebSocket('ws://'+(location.host||'localhost:3000')+'/__livereload');s.onmessage=function(e){if(e.data==='reload')location.reload();};})();</script>`;

const MIME: Record<string, string> = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css",
  ".js": "application/javascript",
  ".json": "application/json",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".gif": "image/gif",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
  ".xml": "application/xml",
};

export function createDevServer(config: SiteConfig, port: number): { server: ReturnType<typeof createServer>; reload: () => void } {
  const clients = new Set<WebSocket>();

  const server = createServer((req: IncomingMessage, res: ServerResponse) => {
    const url = new URL(req.url || "/", `http://localhost:${port}`);
    let filePath = join(config.output, url.pathname);

    if (filePath.endsWith("/") || !extname(filePath)) {
      filePath = join(filePath, "index.html");
    }

    if (!existsSync(filePath) || !statSync(filePath).isFile()) {
      filePath = join(config.output, "index.html");
    }

    if (!existsSync(filePath)) {
      res.writeHead(404);
      res.end("Not found");
      return;
    }

    const ext = extname(filePath);
    const mime = MIME[ext] || "application/octet-stream";

    try {
      let content = readFileSync(filePath);
      if (ext === ".html" || mime.startsWith("text/html")) {
        let html = content.toString("utf-8");
        if (!html.includes("__livereload")) {
          html = html.replace("</body>", RELOAD_SCRIPT + "</body>");
        }
        content = Buffer.from(html);
      }
      res.writeHead(200, { "Content-Type": mime });
      res.end(content);
    } catch {
      res.writeHead(500);
      res.end("Internal server error");
    }
  });

  const wss = new WebSocketServer({ noServer: true });

  server.on("upgrade", (req, socket, head) => {
    if (req.url === "/__livereload") {
      wss.handleUpgrade(req, socket, head, (ws) => {
        clients.add(ws);
        ws.on("close", () => clients.delete(ws));
      });
    } else {
      socket.destroy();
    }
  });

  function reload() {
    const msg = JSON.stringify("reload");
    for (const client of clients) {
      if (client.readyState === WebSocket.OPEN) {
        client.send("reload");
      }
    }
  }

  return { server, reload };
}
