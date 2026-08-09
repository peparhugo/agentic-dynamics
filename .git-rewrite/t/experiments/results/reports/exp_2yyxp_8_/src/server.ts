import * as http from "http";
import * as fs from "fs";
import * as path from "path";
import { WebSocketServer, WebSocket } from "ws";

const LIVE_RELOAD_SCRIPT = `
<script>
(function() {
  var ws = new WebSocket('ws://' + location.host + '/__livereload');
  ws.onmessage = function(msg) {
    if (msg.data === 'reload') {
      location.reload();
    }
  };
  ws.onclose = function() {
    console.log('[live-reload] disconnected, retrying in 1s...');
    setTimeout(function() { location.reload(); }, 1000);
  };
})();
</script>
`;

const mimeTypes: Record<string, string> = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css",
  ".js": "application/javascript",
  ".json": "application/json",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
  ".xml": "application/xml",
};

export function startServer(port: number, outputDir: string): { server: http.Server; reload: () => void } {
  const server = http.createServer((req, res) => {
    const url = req.url ?? "/";
    const filePath = url === "/" ? "/index.html" : url;

    const fullPath = path.join(outputDir, filePath);
    const ext = path.extname(fullPath).toLowerCase();

    if (!fs.existsSync(fullPath) || fs.statSync(fullPath).isDirectory()) {
      const indexPath = path.join(fullPath, "index.html");
      if (fs.existsSync(indexPath)) {
        serveFile(indexPath, ".html", res);
        return;
      }
      res.writeHead(404);
      res.end("Not Found");
      return;
    }

    serveFile(fullPath, ext, res);
  });

  const wss = new WebSocketServer({ server });
  const clients: Set<WebSocket> = new Set();

  wss.on("connection", (ws) => {
    clients.add(ws);
    ws.on("close", () => clients.delete(ws));
  });

  function serveFile(filePath: string, ext: string, res: http.ServerResponse): void {
    const mime = mimeTypes[ext] || "application/octet-stream";
    let content = fs.readFileSync(filePath, "utf-8");

    if (ext === ".html") {
      content = content.replace("</body>", `${LIVE_RELOAD_SCRIPT}</body>`);
    }

    res.writeHead(200, { "Content-Type": mime });
    res.end(content);
  }

  server.listen(port, () => {
    console.log(`Dev server running at http://localhost:${port}`);
  });

  return {
    server,
    reload() {
      for (const client of clients) {
        if (client.readyState === WebSocket.OPEN) {
          client.send("reload");
        }
      }
    },
  };
}
