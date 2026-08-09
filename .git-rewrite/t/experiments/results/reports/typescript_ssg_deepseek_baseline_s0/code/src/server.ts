import { WebSocketServer, WebSocket } from "ws";
import * as http from "node:http";
import * as fs from "node:fs";
import * as path from "node:path";
import chokidar from "chokidar";

const RELOAD_SCRIPT = `
<script>
(function() {
  var ws = new WebSocket('ws://localhost:__PORT__');
  ws.onmessage = function(msg) {
    if (msg.data === 'reload') location.reload();
  };
  ws.onclose = function() {
    setTimeout(function() {
      window.location.reload();
    }, 2000);
  };
})();
</script>
`;

export function injectReloadScript(html: string, port: number): string {
  const script = RELOAD_SCRIPT.replace("__PORT__", String(port));
  if (html.includes("</body>")) {
    return html.replace("</body>", script + "</body>");
  }
  return html + script;
}

const MIME: Record<string, string> = {
  ".html": "text/html",
  ".css": "text/css",
  ".js": "application/javascript",
  ".json": "application/json",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
  ".xml": "application/xml",
};

function serveFile(
  filePath: string,
  res: http.ServerResponse
): void {
  try {
    const stat = fs.statSync(filePath);
    if (stat.isDirectory()) {
      const indexPath = path.join(filePath, "index.html");
      if (fs.existsSync(indexPath)) {
        filePath = indexPath;
      } else {
        res.writeHead(404);
        res.end("Not Found");
        return;
      }
    }
    const ext = path.extname(filePath).toLowerCase();
    const contentType = MIME[ext] || "application/octet-stream";
    const content = fs.readFileSync(filePath);
    res.writeHead(200, { "Content-Type": contentType });
    res.end(content);
  } catch {
    res.writeHead(404);
    res.end("Not Found");
  }
}

export function startDevServer(
  outputDir: string,
  sourceDir: string,
  templateDir: string,
  port: number,
  rebuild: () => Promise<void>
): void {
  const wss = new WebSocketServer({ port: port + 1 });
  let clients: WebSocket[] = [];

  wss.on("connection", (ws) => {
    clients.push(ws);
    ws.on("close", () => {
      clients = clients.filter((c) => c !== ws);
    });
  });

  function broadcastReload(): void {
    for (const client of clients) {
      if (client.readyState === WebSocket.OPEN) {
        client.send("reload");
      }
    }
  }

  const server = http.createServer((req, res) => {
    const urlPath = req.url === "/" ? "/index.html" : req.url ?? "/";
    const filePath = path.join(outputDir, urlPath);
    serveFile(filePath, res);
  });

  server.listen(port, () => {
    const liveReloadPort = port + 1;
    process.stdout.write(
      `Dev server running at http://localhost:${port}\nLive reload on ws://localhost:${liveReloadPort}\n`
    );
  });

  const watcher = chokidar.watch(
    [sourceDir, templateDir],
    {
      ignoreInitial: true,
      awaitWriteFinish: { stabilityThreshold: 200, pollInterval: 50 },
    }
  );

  watcher.on("all", async (_event: string, _filePath: string) => {
    try {
      await rebuild();
      broadcastReload();
      process.stdout.write(`Rebuilt at ${new Date().toLocaleTimeString()}\n`);
    } catch (err) {
      process.stderr.write(`Build error: ${err}\n`);
    }
  });
}
