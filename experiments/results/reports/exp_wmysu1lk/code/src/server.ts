import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { WebSocketServer, WebSocket } from "ws";

const RELOAD_SCRIPT = `<script>
(function(){
  var ws = new WebSocket('ws://' + location.host + '/__reload__');
  ws.onmessage = function(msg) {
    if (msg.data === 'reload') location.reload();
  };
  ws.onclose = function() { setTimeout(function(){location.reload()}, 1000); };
})();
</script>`;

export function startDevServer(
  outputDir: string,
  port: number,
  onRebuild: () => void
): { wss: WebSocketServer; server: http.Server } {
  const mimeTypes: Record<string, string> = {
    ".html": "text/html",
    ".css": "text/css",
    ".js": "application/javascript",
    ".json": "application/json",
    ".xml": "application/xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".svg": "image/svg+xml",
  };

  const server = http.createServer((req, res) => {
    const url = req.url ?? "/";
    let filePath = path.join(outputDir, url === "/" ? "index.html" : url);

    if (!path.extname(filePath)) {
      filePath += ".html";
    }

    const ext = path.extname(filePath);
    const contentType = mimeTypes[ext] ?? "application/octet-stream";

    try {
      let content = fs.readFileSync(filePath);

      if (ext === ".html" || ext === "") {
        content = Buffer.from(
          content
            .toString("utf-8")
            .replace("</body>", `${RELOAD_SCRIPT}</body>`)
        );
      }

      res.writeHead(200, { "Content-Type": contentType });
      res.end(content);
    } catch {
      res.writeHead(404);
      res.end("Not found");
    }
  });

  const wss = new WebSocketServer({ server });

  wss.on("connection", (ws) => {
    ws.on("message", () => {});
  });

  server.listen(port, () => {
    console.log(`Dev server running at http://localhost:${port}`);
  });

  return { wss, server };
}

export function reloadClients(wss: WebSocketServer): void {
  for (const client of wss.clients) {
    if (client.readyState === WebSocket.OPEN) {
      client.send("reload");
    }
  }
}
