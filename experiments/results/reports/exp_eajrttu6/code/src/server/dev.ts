import http from "http";
import fs from "fs";
import path from "path";
import { WebSocketServer, WebSocket } from "ws";
import chokidar from "chokidar";
import { build } from "../generators/build";
import type { SiteConfig } from "../types";

const LIVE_RELOAD_SCRIPT = `
<script>
(function() {
  var protocol = location.protocol === "https:" ? "wss:" : "ws:";
  var ws = new WebSocket(protocol + "//" + location.host + "/__livereload");
  ws.onmessage = function(msg) {
    if (msg.data === "reload") {
      console.log("[staticsmith] Reloading...");
      location.reload();
    }
  };
  ws.onclose = function() {
    console.log("[staticsmith] Live reload disconnected, attempting reconnect...");
    setTimeout(function() {
      location.reload();
    }, 1500);
  };
})();
</script>
`;

export interface ServeOptions {
  sourceDir: string;
  outputDir: string;
  templatesDir: string;
  site: SiteConfig;
  port: number;
  verbose?: boolean;
}

export function serve(options: ServeOptions): http.Server {
  const { sourceDir, outputDir, templatesDir, site, port } = options;

  const result = build({ sourceDir, outputDir, templatesDir, site });
  if (result !== 0) {
    process.exit(1);
  }

  const server = http.createServer((req, res) => {
    let urlPath = (req.url || "/").split("?")[0];
    if (urlPath === "/") urlPath = "/index.html";

    const filePath = path.join(outputDir, urlPath);

    const ext = path.extname(filePath).toLowerCase();
    const mimeTypes: Record<string, string> = {
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
    const mimeType = mimeTypes[ext] || "application/octet-stream";

    if (!fs.existsSync(filePath)) {
      res.writeHead(404);
      res.end("Not found");
      return;
    }

    let content = fs.readFileSync(filePath);

    if (ext === ".html") {
      content = Buffer.concat([
        content,
        Buffer.from(LIVE_RELOAD_SCRIPT),
      ]);
    }

    res.writeHead(200, { "Content-Type": mimeType });
    res.end(content);
  });

  const wss = new WebSocketServer({ server });

  wss.on("connection", (ws: WebSocket) => {
    ws.send("connected");
  });

  const watcher = chokidar.watch(
    [sourceDir, templatesDir],
    {
      ignoreInitial: true,
    }
  );

  watcher.on("all", () => {
    console.log("[staticsmith] Changes detected, rebuilding...");
    build({ sourceDir, outputDir, templatesDir, site, verbose: options.verbose });
    for (const client of wss.clients) {
      if (client.readyState === WebSocket.OPEN) {
        client.send("reload");
      }
    }
    console.log("[staticsmith] Rebuild complete.");
  });

  server.listen(port, () => {
    console.log(`[staticsmith] Dev server running at http://localhost:${port}`);
    console.log("[staticsmith] Watching for changes...");
  });

  process.on("SIGINT", () => {
    watcher.close();
    wss.close();
    server.close();
    process.exit(0);
  });

  return server;
}
