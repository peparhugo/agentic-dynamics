import http from "http";
import fs from "fs";
import path from "path";
import { WebSocketServer, WebSocket } from "ws";
import chokidar from "chokidar";

const RELOAD_SCRIPT = `
<script>
(function() {
  var ws = new WebSocket('ws://' + location.host + '/__livereload');
  ws.onmessage = function(msg) {
    if (msg.data === 'reload') {
      location.reload();
    }
  };
  ws.onclose = function() {
    setTimeout(function() {
      location.reload();
    }, 2000);
  };
})();
</script>
`;

function injectReloadScript(html: string): string {
  if (html.includes("</body>")) {
    return html.replace("</body>", RELOAD_SCRIPT + "</body>");
  }
  return html + RELOAD_SCRIPT;
}

const MIME_TYPES: Record<string, string> = {
  ".html": "text/html",
  ".css": "text/css",
  ".js": "application/javascript",
  ".json": "application/json",
  ".xml": "application/xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
};

function getMimeType(filePath: string): string {
  const ext = path.extname(filePath).toLowerCase();
  return MIME_TYPES[ext] || "application/octet-stream";
}

export function startDevServer(
  outputDir: string,
  sourceDir: string,
  templateDir: string,
  port: number,
  onRebuild: () => void
): void {
  const sockets = new Set<WebSocket>();

  const server = http.createServer((req, res) => {
    let filePath = path.join(outputDir, req.url || "/");
    if (req.url && req.url.endsWith("/")) {
      filePath = path.join(filePath, "index.html");
    }

    if (!fs.existsSync(filePath) || fs.statSync(filePath).isDirectory()) {
      filePath = path.join(outputDir, "index.html");
    }

    try {
      const content = fs.readFileSync(filePath);
      const mime = getMimeType(filePath);
      res.writeHead(200, { "Content-Type": mime });

      if (mime === "text/html") {
        res.end(injectReloadScript(content.toString()));
      } else {
        res.end(content);
      }
    } catch {
      res.writeHead(404);
      res.end("Not Found");
    }
  });

  const wss = new WebSocketServer({ server });

  wss.on("connection", (ws) => {
    sockets.add(ws);
    ws.on("close", () => sockets.delete(ws));
  });

  function broadcastReload(): void {
    for (const ws of sockets) {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send("reload");
      }
    }
  }

  const watchDirs = [
    path.resolve(sourceDir),
    path.resolve(templateDir),
  ];

  const watcher = chokidar.watch(watchDirs, {
    ignoreInitial: true,
    awaitWriteFinish: {
      stabilityThreshold: 100,
      pollInterval: 50,
    },
  });

  watcher.on("all", (_event: string, _filePath: string) => {
    try {
      onRebuild();
      broadcastReload();
    } catch (err) {
      console.error("Rebuild error:", err instanceof Error ? err.message : err);
    }
  });

  server.listen(port, () => {
    console.log(`Dev server running at http://localhost:${port}`);
  });
}
