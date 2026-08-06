import http from "node:http";
import fs from "node:fs/promises";
import path from "node:path";
import { WebSocketServer } from "ws";
import type { AddressInfo } from "node:net";

export function createDevServer(outputDir: string, port: number): http.Server {
  const mimeTypes: Record<string, string> = {
    ".html": "text/html",
    ".css": "text/css",
    ".js": "application/javascript",
    ".json": "application/json",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".xml": "application/xml",
    ".ico": "image/x-icon",
  };

  const server = http.createServer(async (req, res) => {
    let urlPath = req.url || "/";

    // Strip query string
    const qIdx = urlPath.indexOf("?");
    if (qIdx !== -1) urlPath = urlPath.slice(0, qIdx);

    if (urlPath === "/") urlPath = "/index.html";

    const filePath = path.join(outputDir, urlPath);
    try {
      const stat = await fs.stat(filePath);
      if (stat.isDirectory()) {
        const indexFile = path.join(filePath, "index.html");
        try {
          await fs.access(indexFile);
          const content = await fs.readFile(indexFile);
          res.writeHead(200, { "Content-Type": "text/html" });
          res.end(content);
          return;
        } catch {
          res.writeHead(404);
          res.end("Not Found");
          return;
        }
      }

      const ext = path.extname(filePath).toLowerCase();
      const contentType = mimeTypes[ext] || "application/octet-stream";
      const content = await fs.readFile(filePath);
      res.writeHead(200, { "Content-Type": contentType });
      res.end(content);
    } catch {
      res.writeHead(404);
      res.end("Not Found");
    }
  });

  const wss = new WebSocketServer({ server, path: "/__reload" });

  // Heartbeat to keep connections alive
  const interval = setInterval(() => {
    wss.clients.forEach((ws) => {
      if ((ws as any).isAlive === false) return ws.terminate();
      (ws as any).isAlive = false;
      ws.ping();
    });
  }, 30000);

  wss.on("connection", (ws) => {
    (ws as any).isAlive = true;
    ws.on("pong", () => {
      (ws as any).isAlive = true;
    });
  });

  wss.on("close", () => clearInterval(interval));

  return server;
}

export function broadcastReload(server: http.Server): void {
  // Access WebSocketServer attached to the http server
  const wss = (server as any)._wss as WebSocketServer | undefined;
  // Hmm, we attached the WSS to the server via the `server` option, but it's not
  // directly accessible. Let's store it differently.
}

/**
 * Create a reload broadcaster attached to the given server.
 */
export function createReloadBroadcaster(server: http.Server): {
  broadcast: () => void;
  wss: WebSocketServer;
} {
  const wss = new WebSocketServer({ noServer: true });

  server.on("upgrade", (request, socket, head) => {
    if (request.url === "/__reload") {
      wss.handleUpgrade(request, socket, head, (ws) => {
        wss.emit("connection", ws, request);
      });
    } else {
      socket.destroy();
    }
  });

  setInterval(() => {
    wss.clients.forEach((ws) => {
      if ((ws as any).isAlive === false) return ws.terminate();
      (ws as any).isAlive = false;
      ws.ping();
    });
  }, 30000);

  wss.on("connection", (ws) => {
    (ws as any).isAlive = true;
    ws.on("pong", () => {
      (ws as any).isAlive = true;
    });
  });

  return {
    broadcast() {
      for (const client of wss.clients) {
        if (client.readyState === 1) {
          client.send("reload");
        }
      }
    },
    wss,
  };
}
