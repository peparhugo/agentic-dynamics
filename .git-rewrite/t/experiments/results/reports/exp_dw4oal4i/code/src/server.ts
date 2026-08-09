import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import { readFileSync, existsSync, watch } from "node:fs";
import { join, extname } from "node:path";
import { WebSocketServer, WebSocket } from "ws";
import { build } from "./ssg.js";

const RELOAD_SCRIPT = `
<script>
(function() {
  var ws = new WebSocket('ws://' + location.host + '/__reload');
  ws.onmessage = function(e) {
    if (e.data === 'reload') location.reload();
  };
  ws.onclose = function() {
    setTimeout(function() {
      new WebSocket('ws://' + location.host + '/__reload');
    }, 1000);
  };
})();
</script>`;

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

function serveFile(path: string, res: ServerResponse, injectReload: boolean) {
  if (!existsSync(path)) return false;
  let content = readFileSync(path);
  const ext = extname(path);
  const mime = MIME[ext] ?? "application/octet-stream";
  if (injectReload && mime === "text/html") {
    const s = content.toString("utf-8");
    // Insert reload script before </body>
    content = Buffer.from(s.replace("</body>", RELOAD_SCRIPT + "</body>"));
  }
  res.writeHead(200, { "Content-Type": mime, "Cache-Control": "no-cache" });
  res.end(content);
  return true;
}

export function serve(outputDir: string, sourceDir: string, templateDir: string, port: number) {
  const wss = new WebSocketServer({ noServer: true });
  const sockets = new Set<WebSocket>();

  wss.on("connection", (ws) => {
    sockets.add(ws);
    ws.on("close", () => sockets.delete(ws));
  });

  function reload() {
    for (const ws of sockets) {
      ws.send("reload");
    }
  }

  function rebuild() {
    try {
      build(sourceDir, templateDir, outputDir);
      console.log("  [rebuilt]");
      reload();
    } catch (e) {
      console.error("  [build error]", e);
    }
  }

  const watcher = watch(sourceDir, { recursive: true }, (event, filename) => {
    if (filename?.endsWith(".md")) {
      console.log(`  [${event}] ${filename}`);
      rebuild();
    }
  });

  const templateWatcher = watch(templateDir, { recursive: true }, () => {
    console.log("  [template change]");
    rebuild();
  });

  const httpServer = createServer((req: IncomingMessage, res: ServerResponse) => {
    const url = new URL(req.url ?? "/", `http://localhost:${port}`);
    let pathname = url.pathname;

    if (pathname === "/__reload") {
      // handled by upgrade
      res.writeHead(404);
      res.end();
      return;
    }

    if (pathname === "/") pathname = "/index.html";
    let filePath = join(outputDir, pathname);

    if (!existsSync(filePath)) {
      // try index.html in directory
      if (!extname(pathname)) {
        filePath = join(outputDir, pathname, "index.html");
      }
    }

    if (serveFile(filePath, res, true)) return;
    res.writeHead(404);
    res.end("Not found");
  });

  httpServer.on("upgrade", (req, socket, head) => {
    const url = new URL(req.url ?? "/", `http://localhost:${port}`);
    if (url.pathname === "/__reload") {
      wss.handleUpgrade(req, socket, head, (ws) => {
        wss.emit("connection", ws, req);
      });
    } else {
      socket.destroy();
    }
  });

  httpServer.listen(port, () => {
    console.log(`  Dev server at http://localhost:${port}`);
  });

  return { httpServer, watcher, templateWatcher, wss, rebuild };
}
