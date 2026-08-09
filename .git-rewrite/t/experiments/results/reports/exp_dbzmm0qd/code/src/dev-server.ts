import { createServer, IncomingMessage, ServerResponse } from "node:http";
import { readFileSync, existsSync, statSync } from "node:fs";
import { join, extname } from "node:path";
import { WebSocketServer, WebSocket } from "ws";
import { SiteConfig } from "./types.js";
import { build } from "./build.js";

const RELOAD_SCRIPT = `
<script>
(function() {
  var ws = new WebSocket('ws://' + location.host);
  ws.onmessage = function(msg) {
    if (msg.data === 'reload') location.reload();
  };
  ws.onclose = function() {
    setTimeout(function() {
      location.reload();
    }, 2000);
  };
})();
</script>`;

let wss: WebSocketServer;

export function startDevServer(config: SiteConfig, port: number = 3000): void {
  const server = createServer((req: IncomingMessage, res: ServerResponse) => {
    handleRequest(req, res, config);
  });

  wss = new WebSocketServer({ server });

  server.listen(port, () => {
    console.log(`Dev server running at http://localhost:${port}`);
  });
}

export function reloadClients(): void {
  if (!wss) return;
  wss.clients.forEach((client) => {
    if (client.readyState === WebSocket.OPEN) {
      client.send("reload");
    }
  });
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

function handleRequest(
  req: IncomingMessage,
  res: ServerResponse,
  config: SiteConfig
): void {
  let urlPath = req.url ?? "/";
  if (urlPath === "/") urlPath = "/index.html";

  const filePath = join(config.outputDir, urlPath);

  if (!existsSync(filePath) || !statSync(filePath).isFile()) {
    res.writeHead(404);
    res.end("Not found");
    return;
  }

  const ext = extname(filePath);
  const contentType = MIME[ext] ?? "application/octet-stream";

  let body = readFileSync(filePath);

  if (contentType === "text/html") {
    const html = body.toString("utf-8");
    const injected = html.replace("</body>", `${RELOAD_SCRIPT}</body>`);
    res.writeHead(200, {
      "Content-Type": "text/html",
      "Content-Length": Buffer.byteLength(injected),
    });
    res.end(injected);
  } else {
    res.writeHead(200, {
      "Content-Type": contentType,
      "Content-Length": body.length,
    });
    res.end(body);
  }
}
