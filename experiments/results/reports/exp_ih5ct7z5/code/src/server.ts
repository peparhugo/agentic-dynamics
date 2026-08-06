import http from "http";
import fs from "fs";
import path from "path";
import { WebSocketServer, WebSocket } from "ws";
import chokidar from "chokidar";
import { generateSite } from "./generator";
import { SiteConfig } from "./types";

const RELOAD_SCRIPT = `
<script>
(function() {
  var ws = new WebSocket('ws://' + location.host + '/__livereload');
  ws.onmessage = function(msg) {
    if (msg.data === 'reload') {
      ws.close();
      location.reload();
    }
  };
  ws.onclose = function() {
    setTimeout(function() {
      var retry = new WebSocket('ws://' + location.host + '/__livereload');
      retry.onmessage = function(msg) {
        if (msg.data === 'reload') location.reload();
      };
    }, 1000);
  };
})();
</script>
`;

export function startDevServer(
  sourceDir: string,
  templateDir: string,
  outputDir: string,
  port: number,
  config: SiteConfig
): void {
  console.log(`Building site...`);
  generateSite(sourceDir, templateDir, outputDir, config);

  const server = http.createServer((req, res) => {
    const url = req.url || "/";
    const urlPath = url === "/" ? "/index.html" : url;

    const filePath = path.join(outputDir, urlPath);
    const ext = path.extname(filePath).toLowerCase();

    const mimeTypes: Record<string, string> = {
      ".html": "text/html",
      ".css": "text/css",
      ".js": "application/javascript",
      ".json": "application/json",
      ".png": "image/png",
      ".jpg": "image/jpeg",
      ".svg": "image/svg+xml",
      ".xml": "application/xml",
      ".ico": "image/x-icon",
    };

    const contentType = mimeTypes[ext] || "application/octet-stream";

    try {
      let content = fs.readFileSync(filePath);
      if (contentType === "text/html") {
        let html = content.toString("utf-8");
        html = html.replace("</body>", RELOAD_SCRIPT + "</body>");
        content = Buffer.from(html, "utf-8");
      }
      res.writeHead(200, { "Content-Type": contentType });
      res.end(content);
    } catch {
      res.writeHead(404, { "Content-Type": "text/plain" });
      res.end("Not Found");
    }
  });

  const wss = new WebSocketServer({ server });

  const watcher = chokidar.watch([sourceDir, templateDir], {
    ignoreInitial: true,
    awaitWriteFinish: { stabilityThreshold: 100, pollInterval: 50 },
  });

  const rebuild = () => {
    try {
      console.log("Change detected, rebuilding...");
      generateSite(sourceDir, templateDir, outputDir, config);
      console.log("Site rebuilt. Reloading browsers...");
      wss.clients.forEach((client) => {
        if (client.readyState === WebSocket.OPEN) {
          client.send("reload");
        }
      });
    } catch (err) {
      console.error("Build error:", err);
    }
  };

  let rebuildTimeout: NodeJS.Timeout | null = null;
  watcher.on("change", () => {
    if (rebuildTimeout) clearTimeout(rebuildTimeout);
    rebuildTimeout = setTimeout(rebuild, 300);
  });
  watcher.on("add", () => {
    if (rebuildTimeout) clearTimeout(rebuildTimeout);
    rebuildTimeout = setTimeout(rebuild, 300);
  });
  watcher.on("unlink", () => {
    if (rebuildTimeout) clearTimeout(rebuildTimeout);
    rebuildTimeout = setTimeout(rebuild, 300);
  });

  server.listen(port, () => {
    console.log(`Dev server running at http://localhost:${port}/`);
  });
}
