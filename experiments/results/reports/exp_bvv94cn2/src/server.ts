import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import { readFileSync, existsSync } from "node:fs";
import { join, extname } from "node:path";
import { WebSocketServer, WebSocket } from "ws";
import { watch } from "chokidar";
import type { SiteConfig } from "./types.js";
import { build } from "./build.js";

const RELOAD_SCRIPT = `
<script>
(function(){
  var ws = new WebSocket('ws://' + location.host + '/__ssg_reload');
  ws.onmessage = function(msg) {
    if (msg.data === 'reload') location.reload();
  };
  ws.onclose = function() {
    setTimeout(function() {
      window.location.reload();
    }, 1000);
  };
})();
</script>
`;

const MIME: Record<string, string> = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css",
  ".js": "application/javascript",
  ".json": "application/json",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".svg": "image/svg+xml",
  ".xml": "application/xml",
  ".ico": "image/x-icon",
};

function injectReload(body: string): string {
  if (body.includes("</body>")) {
    return body.replace("</body>", RELOAD_SCRIPT + "</body>");
  }
  return body + RELOAD_SCRIPT;
}

export async function startServer(
  config: SiteConfig,
  port: number = 3000,
  sourceDir?: string,
  templateDir?: string
): Promise<void> {
  let wss: WebSocketServer;

  const server = createServer((req: IncomingMessage, res: ServerResponse) => {
    const url = req.url ?? "/";
    let filePath = join(config.outputDir, url === "/" ? "index.html" : url);

    // Fallback for clean URLs
    if (!existsSync(filePath) || filePath.endsWith("/")) {
      const htmlPath = join(filePath, "index.html");
      if (existsSync(htmlPath)) {
        filePath = htmlPath;
      }
    }

    const ext = extname(filePath);
    const mime = MIME[ext] || "application/octet-stream";

    try {
      let body = readFileSync(filePath, "utf-8");
      if (mime.startsWith("text/html")) {
        body = injectReload(body);
      }
      res.writeHead(200, { "Content-Type": mime });
      res.end(body);
    } catch {
      res.writeHead(404, { "Content-Type": "text/plain" });
      res.end("Not found");
    }
  });

  wss = new WebSocketServer({ server });

  let clients: WebSocket[] = [];
  wss.on("connection", (ws) => {
    clients.push(ws);
    ws.on("close", () => {
      clients = clients.filter(c => c !== ws);
    });
  });

  function reloadAll() {
    for (const client of clients) {
      try { client.send("reload"); } catch { /* ignore */ }
    }
  }

  // Watch source and template dirs
  const watchDirs: string[] = [sourceDir ?? config.sourceDir];
  if (templateDir ?? config.templateDir) {
    watchDirs.push(templateDir ?? config.templateDir);
  }

  const watcher = watch(watchDirs, {
    ignored: /(^|[/\\])\../, // dotfiles
    persistent: true,
  });

  let rebuildTimer: ReturnType<typeof setTimeout> | null = null;
  const scheduleRebuild = () => {
    if (rebuildTimer) clearTimeout(rebuildTimer);
    rebuildTimer = setTimeout(async () => {
      try {
        await build(config);
        reloadAll();
      } catch (err) {
        console.error("Rebuild error:", err);
      }
    }, 150);
  };

  watcher.on("change", scheduleRebuild);
  watcher.on("add", scheduleRebuild);
  watcher.on("unlink", scheduleRebuild);

  server.listen(port, () => {
    console.log(`Dev server running at http://localhost:${port}`);
    console.log(`Live reload enabled`);
  });
}
