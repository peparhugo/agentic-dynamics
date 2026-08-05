import { createServer, IncomingMessage, ServerResponse } from "node:http";
import { readFileSync, existsSync, statSync } from "node:fs";
import { join, extname } from "node:path";
import { WebSocketServer, WebSocket } from "ws";
import chokidar from "chokidar";
import type { BuilderOptions } from "./types.js";
import { build } from "./build.js";

const MIME: Record<string, string> = {
  ".html": "text/html",
  ".css": "text/css",
  ".js": "application/javascript",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
  ".xml": "application/xml",
  ".json": "application/json",
};

const RELOAD_SCRIPT = `
<script>(function(){
  var ws=new WebSocket('ws://'+location.host);
  ws.onmessage=function(e){if(e.data==='reload')location.reload();};
})();</script>`;

let wss: WebSocketServer;

function serveFile(res: ServerResponse, filePath: string): void {
  if (!existsSync(filePath)) {
    res.writeHead(404);
    res.end("Not found");
    return;
  }
  const ext = extname(filePath);
  const mime = MIME[ext] || "application/octet-stream";
  let data = readFileSync(filePath);

  if (ext === ".html") {
    data = Buffer.from(data.toString() + RELOAD_SCRIPT);
  }

  res.writeHead(200, {
    "Content-Type": mime,
    "Content-Length": data.length,
    "Cache-Control": "no-cache",
  });
  res.end(data);
}

export function startServer(opts: BuilderOptions, port: number = 3000): void {
  build(opts);

  const watcher = chokidar.watch([opts.sourceDir, opts.templateDir], {
    ignoreInitial: true,
  });

  const rebuild = () => {
    try {
      build(opts);
      if (wss) {
        for (const client of wss.clients) {
          if (client.readyState === WebSocket.OPEN) client.send("reload");
        }
      }
    } catch (e) {
      console.error("Build error:", e);
    }
  };

  watcher.on("all", rebuild);

  const server = createServer((req: IncomingMessage, res: ServerResponse) => {
    const url = req.url === "/" ? "/index.html" : req.url ?? "/index.html";
    const filePath = join(opts.outputDir, url);
    if (existsSync(filePath) && statSync(filePath).isFile()) {
      serveFile(res, filePath);
    } else if (existsSync(filePath) && statSync(filePath).isDirectory()) {
      serveFile(res, join(filePath, "index.html"));
    } else {
      serveFile(res, join(opts.outputDir, "index.html"));
    }
  });

  wss = new WebSocketServer({ server });
  wss.on("connection", (ws) => {
    ws.send("connected");
  });

  server.listen(port, () => {
    console.log(`Dev server at http://localhost:${port}`);
  });
}
