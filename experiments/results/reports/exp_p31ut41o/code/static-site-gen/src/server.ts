import { createServer, IncomingMessage, ServerResponse } from "node:http";
import { readFileSync, existsSync, statSync } from "node:fs";
import { join, extname } from "node:path";
import { WebSocketServer, WebSocket } from "ws";
import type { Server } from "node:http";
import type { SiteConfig } from "./types.js";

const RELOAD_SCRIPT = `
<script>
(function() {
  var ws = new WebSocket('ws://' + location.host + '/__livereload');
  ws.onmessage = function(msg) {
    if (msg.data === 'reload') location.reload();
  };
  ws.onclose = function() { setTimeout(function() { location.reload(); }, 2000); };
})();
</script>`;

const MIME_TYPES: Record<string, string> = {
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

export interface DevServer {
  http: Server;
  reload: () => void;
}

export function startDevServer(config: SiteConfig, port: number = 3000): Promise<DevServer> {
  return new Promise((resolve) => {
    const wss = new WebSocketServer({ noServer: true });
    const sockets = new Set<WebSocket>();

    wss.on("connection", (ws) => {
      sockets.add(ws);
      ws.on("close", () => sockets.delete(ws));
    });

    function notifyReload() {
      for (const ws of sockets) {
        ws.send("reload");
      }
    }

    const server = createServer((req: IncomingMessage, res: ServerResponse) => {
      const url = new URL(req.url || "/", `http://localhost:${port}`);
      let filePath = join(config.outputDir, url.pathname);

      if (url.pathname === "/" || url.pathname.endsWith("/")) {
        filePath = join(filePath, "index.html");
      }

      if (!existsSync(filePath)) {
        res.writeHead(404);
        res.end("Not found");
        return;
      }

      const stats = statSync(filePath);
      if (stats.isDirectory()) {
        filePath = join(filePath, "index.html");
      }

      if (!existsSync(filePath)) {
        res.writeHead(404);
        res.end("Not found");
        return;
      }

      const ext = extname(filePath).toLowerCase();
      const mime = MIME_TYPES[ext] || "application/octet-stream";

      let content = readFileSync(filePath, "utf-8");
      if (ext === ".html") {
        content = content.replace("</body>", `${RELOAD_SCRIPT}</body>`);
      }

      res.writeHead(200, { "Content-Type": mime, "Content-Length": Buffer.byteLength(content) });
      res.end(content);
    });

    server.on("upgrade", (req, socket, head) => {
      if (req.url === "/__livereload") {
        wss.handleUpgrade(req, socket, head, (ws) => {
          wss.emit("connection", ws, req);
        });
      } else {
        socket.destroy();
      }
    });

    server.listen(port, () => {
      console.log(`Dev server running at http://localhost:${port}`);
      resolve({ http: server, reload: notifyReload });
    });
  });
}

export { RELOAD_SCRIPT };
