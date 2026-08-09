import http from "node:http";
import fs from "node:fs/promises";
import path from "node:path";
import { WebSocketServer, WebSocket } from "ws";
import { watch } from "chokidar";

const RELOAD_SCRIPT = `
<script>
(function() {
  var socket = new WebSocket('ws://' + location.host + '/__livereload');
  socket.onmessage = function(msg) {
    if (msg.data === 'reload') location.reload();
  };
})();
</script>
</body>`;

function injectReloadScript(html: string): string {
  return html.replace("</body>", RELOAD_SCRIPT);
}

export async function startDevServer(
  outputDir: string,
  sourceDir: string,
  rebuild: () => Promise<void>,
  port: number = 8080,
): Promise<{ server: http.Server; wss: WebSocketServer }> {
  const server = http.createServer(async (req, res) => {
    let urlPath = req.url ?? "/";
    if (urlPath === "/") urlPath = "/index.html";

    const filePath = path.join(outputDir, urlPath);

    try {
      const content = await fs.readFile(filePath);
      const ext = path.extname(filePath);
      const mimeTypes: Record<string, string> = {
        ".html": "text/html",
        ".css": "text/css",
        ".js": "application/javascript",
        ".xml": "application/xml",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".svg": "image/svg+xml",
      };
      const contentType = mimeTypes[ext] ?? "application/octet-stream";

      let body = content;
      if (ext === ".html") {
        body = Buffer.from(injectReloadScript(content.toString()));
      }

      res.writeHead(200, { "Content-Type": contentType });
      res.end(body);
    } catch {
      res.writeHead(404);
      res.end("Not found");
    }
  });

  const wss = new WebSocketServer({ server });

  wss.on("connection", (ws: WebSocket) => {
    ws.send("connected");
  });

  function triggerReload() {
    for (const client of wss.clients) {
      if (client.readyState === WebSocket.OPEN) {
        client.send("reload");
      }
    }
  }

  const watcher = watch(sourceDir, {
    ignoreInitial: true,
  });

  watcher.on("all", async (_event, _filePath) => {
    try {
      await rebuild();
      triggerReload();
    } catch (err) {
      console.error("Build error:", err);
    }
  });

  return new Promise((resolve) => {
    server.listen(port, () => {
      console.log(`Dev server running at http://localhost:${port}`);
      resolve({ server, wss });
    });
  });
}
