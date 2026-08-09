import http from "node:http";
import { readFile, access } from "node:fs/promises";
import { join, extname } from "node:path";
import { WebSocketServer, WebSocket } from "ws";
import chokidar from "chokidar";
import type { SiteConfig } from "./types.js";
import { generate } from "./generator.js";

const RELOAD_SCRIPT = `
<script>
(function() {
  var socket = new WebSocket('ws://' + location.host + '/__ssg_reload');
  socket.onmessage = function(msg) {
    if (msg.data === 'reload') location.reload();
  };
  socket.onclose = function() {
    setTimeout(function() {
      location.reload();
    }, 2000);
  };
})();
</script>`;

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
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".svg": "image/svg+xml",
  ".xml": "application/xml",
  ".woff2": "font/woff2",
};

export async function startDevServer(config: SiteConfig, port = 3000): Promise<http.Server> {
  let wss: WebSocketServer;
  let clients = new Set<WebSocket>();

  await generate(config);

  const server = http.createServer(async (req, res) => {
    const url = req.url ?? "/";
    const filePath =
      url === "/" || url.endsWith("/")
        ? join(config.outputDir, url, "index.html")
        : join(config.outputDir, url);

    try {
      await access(filePath);
      const content = await readFile(filePath);
      const ext = extname(filePath);
      const contentType = MIME_TYPES[ext] ?? "application/octet-stream";
      res.writeHead(200, { "Content-Type": contentType });

      if (ext === ".html" || filePath.endsWith("/index.html")) {
        res.end(injectReloadScript(content.toString()));
      } else {
        res.end(content);
      }
    } catch {
      res.writeHead(200, { "Content-Type": "text/html" });
      const indexPath = join(config.outputDir, "index.html");
      try {
        await access(indexPath);
        const html = await readFile(indexPath, "utf-8");
        res.end(injectReloadScript(html));
      } catch {
        res.writeHead(404);
        res.end("Not found");
      }
    }
  });

  wss = new WebSocketServer({ server, path: "/__ssg_reload" });

  wss.on("connection", (ws) => {
    clients.add(ws);
    ws.on("close", () => clients.delete(ws));
  });

  const broadcast = () => {
    const msg = JSON.stringify("reload");
    for (const client of clients) {
      if (client.readyState === WebSocket.OPEN) {
        client.send("reload");
      }
    }
  };

  const watcher = chokidar.watch(
    [config.sourceDir, config.templateDir],
    {
      ignoreInitial: true,
      awaitWriteFinish: { stabilityThreshold: 100, pollInterval: 50 },
    }
  );

  let rebuildTimer: ReturnType<typeof setTimeout> | null = null;

  watcher.on("all", async () => {
    if (rebuildTimer) clearTimeout(rebuildTimer);
    rebuildTimer = setTimeout(async () => {
      try {
        await generate(config);
        broadcast();
      } catch (err) {
        console.error("Build error:", err);
      }
    }, 100);
  });

  return new Promise((resolve) => {
    server.listen(port, () => {
      console.log(`Dev server running at http://localhost:${port}`);
      resolve(server);
    });
  });
}
