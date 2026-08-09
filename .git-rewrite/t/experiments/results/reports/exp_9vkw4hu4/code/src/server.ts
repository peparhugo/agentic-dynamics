import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { WebSocketServer } from "ws";
import chokidar from "chokidar";
import { buildSite } from "./site.js";
import type { SiteConfig } from "./site.js";

const RELOAD_SCRIPT = `
<script>
(function(){
  var socket = new WebSocket('ws://' + location.host);
  socket.onmessage = function(msg) {
    if (msg.data === 'reload') location.reload();
  };
})();
</script>
`;

export function startDevServer(config: SiteConfig, port: number = 8080): http.Server {
  const wss = new WebSocketServer({ noServer: true });

  const clients = new Set<import("ws").WebSocket>();
  wss.on("connection", (ws) => {
    clients.add(ws);
    ws.on("close", () => clients.delete(ws));
  });

  function reloadAll() {
    for (const ws of clients) {
      ws.send("reload");
    }
  }

  const inferredRenderer = await import("./renderer.js");

  const server = http.createServer((req, res) => {
    const outDir = config.outputDir;
    const url = req.url === "/" ? "/index.html" : req.url ?? "/index.html";
    const filePath = path.join(outDir, url);

    if (!fs.existsSync(filePath)) {
      res.writeHead(404);
      res.end("Not Found");
      return;
    }

    let content = fs.readFileSync(filePath, "utf-8");
    if (filePath.endsWith(".html")) {
      content = content.replace("</body>", RELOAD_SCRIPT + "</body>");
    }

    const mimeTypes: Record<string, string> = {
      ".html": "text/html",
      ".css": "text/css",
      ".js": "application/javascript",
      ".xml": "application/xml",
      ".png": "image/png",
      ".jpg": "image/jpeg",
      ".svg": "image/svg+xml",
    };
    const ext = path.extname(filePath);
    res.writeHead(200, { "Content-Type": mimeTypes[ext] ?? "text/plain" });
    res.end(content);
  });

  let rebuildTimeout: ReturnType<typeof setTimeout>;
  const watcher = chokidar.watch([config.sourceDir, config.templateDir], {
    ignoreInitial: true,
  });

  watcher.on("all", (_event, _filePath) => {
    clearTimeout(rebuildTimeout);
    rebuildTimeout = setTimeout(async () => {
      try {
        await buildSite(config);
        reloadAll();
      } catch (e) {
        console.error("Build error:", e);
      }
    }, 200);
  });

  server.on("upgrade", (req, socket, head) => {
    wss.handleUpgrade(req, socket, head, (ws) => {
      wss.emit("connection", ws, req);
    });
  });

  server.listen(port);
  return server;
}
