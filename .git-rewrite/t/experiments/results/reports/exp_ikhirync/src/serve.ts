import { createServer, IncomingMessage, ServerResponse } from "node:http";
import { readFileSync, existsSync, statSync } from "node:fs";
import { join, extname } from "node:path";
import { WebSocketServer, WebSocket } from "ws";
import { watch } from "chokidar";
import type { ServeOptions } from "./types.js";
import { build } from "./build.js";

const RELOAD_SCRIPT = `
<script>
(function() {
  var ws = new WebSocket('ws://' + location.host + '/__reload');
  ws.onmessage = function(msg) {
    if (msg.data === 'reload') location.reload();
  };
})();
</script>`;

export function serve(options: ServeOptions): void {
  const { source, templates, output, port } = options;

  const contentTypeMap: Record<string, string> = {
    ".html": "text/html",
    ".css": "text/css",
    ".js": "application/javascript",
    ".json": "application/json",
    ".xml": "application/xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
  };

  const server = createServer((req: IncomingMessage, res: ServerResponse) => {
    const url = req.url === "/" ? "/index.html" : req.url ?? "/index.html";
    const filePath = join(output, url);
    if (!existsSync(filePath) || statSync(filePath).isDirectory()) {
      res.writeHead(404);
      res.end("Not found");
      return;
    }

    const ext = extname(filePath);
    const contentType = contentTypeMap[ext] ?? "application/octet-stream";

    let body = readFileSync(filePath, "utf-8");
    if (ext === ".html") {
      body = body.replace("</body>", `${RELOAD_SCRIPT}</body>`);
    }

    res.writeHead(200, { "Content-Type": contentType });
    res.end(body);
  });

  const wss = new WebSocketServer({ server });

  const clients = new Set<WebSocket>();
  wss.on("connection", (ws: WebSocket) => {
    clients.add(ws);
    ws.on("close", () => clients.delete(ws));
  });

  function reload(): void {
    for (const ws of clients) ws.send("reload");
  }

  const watcher = watch([source, templates], {
    ignoreInitial: true,
  });

  watcher.on("change", () => {
    try {
      build({ source, templates, output });
      reload();
    } catch {
      // build failed — keep serving previous build
    }
  });

  server.listen(port, () => {
    console.log(`Dev server listening at http://localhost:${port}`);
  });
}
