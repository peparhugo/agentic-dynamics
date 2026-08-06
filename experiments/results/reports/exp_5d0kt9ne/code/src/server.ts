import http from "http";
import fs from "fs";
import path from "path";
import { WebSocketServer, WebSocket } from "ws";
import chokidar from "chokidar";
import { GeneratorOptions } from "./types";
import { buildSite } from "./generator";

const LIVE_RELOAD_SCRIPT = `
<script>
(function() {
  var ws = new WebSocket('ws://' + location.host + '/__livereload');
  ws.onmessage = function(msg) {
    if (msg.data === 'reload') location.reload();
  };
})();
</script>
`;

export function startDevServer(options: GeneratorOptions): void {
  const watchPaths = [options.sourceDir, options.templateDir];

  buildSite(options);

  const server = http.createServer((req, res) => {
    const url = req.url || "/";
    const filePath = url === "/"
      ? path.join(options.outputDir, "index.html")
      : path.join(options.outputDir, url);

    try {
      let content = fs.readFileSync(filePath, "utf-8");

      // For HTML files inject the livereload script before </body>
      if (filePath.endsWith(".html") && content.includes("</body>")) {
        content = content.replace("</body>", LIVE_RELOAD_SCRIPT + "</body>");
      } else if (filePath.endsWith(".html")) {
        content += LIVE_RELOAD_SCRIPT;
      }

      const mime: Record<string, string> = {
        ".html": "text/html",
        ".css": "text/css",
        ".js": "application/javascript",
        ".json": "application/json",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".svg": "image/svg+xml",
        ".xml": "application/xml",
      };
      const ext = path.extname(filePath);
      res.writeHead(200, { "Content-Type": mime[ext] || "text/plain" });
      res.end(content);
    } catch {
      res.writeHead(404);
      res.end("Not found");
    }
  });

  const wss = new WebSocketServer({ server });
  const clients = new Set<WebSocket>();

  wss.on("connection", (ws) => {
    clients.add(ws);
    ws.on("close", () => clients.delete(ws));
  });

  function broadcastReload() {
    for (const ws of clients) {
      ws.send("reload");
    }
  }

  const watcher = chokidar.watch(watchPaths, {
    ignoreInitial: true,
    awaitWriteFinish: { stabilityThreshold: 300 },
  });

  watcher.on("all", () => {
    try {
      buildSite(options);
      broadcastReload();
    } catch (err) {
      console.error("Build error:", err);
    }
  });

  const port = 3456;
  server.listen(port, () => {
    console.log(`Dev server running at http://localhost:${port}`);
    console.log(`Watching ${options.sourceDir} and ${options.templateDir} for changes`);
  });
}
