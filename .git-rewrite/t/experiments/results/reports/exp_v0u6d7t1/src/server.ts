import http from "node:http";
import fs from "node:fs/promises";
import path from "node:path";
import { WebSocketServer, WebSocket } from "ws";
import chokidar from "chokidar";
import type { CLIOptions } from "./types.js";
import { build } from "./build.js";

const RELOAD_SCRIPT = `
<script>
(function() {
  var ws = new WebSocket('ws://' + location.host + '/__livereload');
  ws.onmessage = function(msg) {
    if (msg.data === 'reload') location.reload();
  };
  ws.onclose = function() {
    setTimeout(function() {
      location.reload();
    }, 2000);
  };
})();
</script>
`;

export async function serve(opts: CLIOptions): Promise<void> {
  await build(opts);

  const wss = new WebSocketServer({ noServer: true });
  const clients = new Set<WebSocket>();

  wss.on("connection", (ws) => {
    clients.add(ws);
    ws.on("close", () => clients.delete(ws));
  });

  function notifyReload() {
    for (const client of clients) {
      if (client.readyState === WebSocket.OPEN) {
        client.send("reload");
      }
    }
  }

  const watcher = chokidar.watch(opts.source, {
    ignoreInitial: true,
    awaitWriteFinish: { stabilityThreshold: 300 },
  });

  watcher.on("all", async () => {
    try {
      await build(opts);
      notifyReload();
    } catch (err) {
      console.error("Build error:", err);
    }
  });

  const server = http.createServer(async (req, res) => {
    if (!req.url) {
      res.writeHead(404);
      res.end();
      return;
    }

    let filePath = path.join(opts.output, req.url === "/" ? "index.html" : req.url);

    try {
      const stat = await fs.stat(filePath);
      if (stat.isDirectory()) {
        filePath = path.join(filePath, "index.html");
      }
    } catch {
      res.writeHead(404);
      res.end("Not found");
      return;
    }

    try {
      const content = await fs.readFile(filePath, "utf-8");
      const injected = filePath.endsWith(".html")
        ? content.replace("</body>", `${RELOAD_SCRIPT}</body>`)
        : content;

      const ext = path.extname(filePath);
      const mimeTypes: Record<string, string> = {
        ".html": "text/html",
        ".css": "text/css",
        ".js": "application/javascript",
        ".xml": "application/xml",
        ".json": "application/json",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".svg": "image/svg+xml",
      };

      res.writeHead(200, {
        "Content-Type": mimeTypes[ext] ?? "application/octet-stream",
      });
      res.end(injected);
    } catch {
      res.writeHead(404);
      res.end("Not found");
    }
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

  server.listen(opts.port, () => {
    console.log(`Dev server running at http://localhost:${opts.port}`);
    console.log(`Watching: ${opts.source}`);
  });
}
