import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { WebSocketServer, WebSocket } from "ws";
import chokidar from "chokidar";
import { build } from "./builder.js";

const RELOAD_SCRIPT = `
<script>
(function(){
  if(window.__ssgLiveReload)return;
  window.__ssgLiveReload=true;
  var ws=new WebSocket('ws://'+(location.host||location.hostname)+'/__livereload');
  ws.onmessage=function(e){if(e.data==='reload')location.reload();};
  ws.onclose=function(){setTimeout(function(){location.reload();},2000);};
})();
</script>
</body>`;

function injectReloadScript(html: string): string {
  if (html.includes("__ssgLiveReload")) return html;
  return html.replace(/<\/body>/i, RELOAD_SCRIPT);
}

const MIME: Record<string, string> = {
  ".html": "text/html",
  ".css": "text/css",
  ".js": "application/javascript",
  ".json": "application/json",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".svg": "image/svg+xml",
  ".xml": "application/xml",
  ".woff2": "font/woff2",
  ".ico": "image/x-icon",
};

export function startDevServer(
  outputDir: string,
  watchDirs: string[],
  port: number,
  rebuild: () => void
): http.Server {
  rebuild();

  const server = http.createServer((req, res) => {
    const url = new URL(req.url ?? "/", `http://localhost:${port}`);
    let fpath = path.join(outputDir, url.pathname);
    if (url.pathname === "/" || url.pathname.endsWith("/")) {
      fpath = path.join(fpath, "index.html");
    }

    const ext = path.extname(fpath).toLowerCase();
    const contentType = MIME[ext] ?? "application/octet-stream";

    try {
      const content = fs.readFileSync(fpath);
      res.writeHead(200, { "Content-Type": contentType });

      if (ext === ".html") {
        const html = injectReloadScript(content.toString("utf-8"));
        res.end(html);
      } else {
        res.end(content);
      }
    } catch {
      res.writeHead(404);
      res.end("Not found");
    }
  });

  const wss = new WebSocketServer({ server });
  const clients = new Set<WebSocket>();

  wss.on("connection", (ws, req) => {
    if (req.url === "/__livereload") {
      clients.add(ws);
      ws.on("close", () => clients.delete(ws));
    }
  });

  watchDirs.forEach((dir) => {
    if (!fs.existsSync(dir)) return;
    chokidar.watch(dir, { ignoreInitial: true }).on("all", () => {
      rebuild();
      for (const client of clients) {
        if (client.readyState === WebSocket.OPEN) {
          client.send("reload");
        }
      }
    });
  });

  server.listen(port);
  return server;
}
