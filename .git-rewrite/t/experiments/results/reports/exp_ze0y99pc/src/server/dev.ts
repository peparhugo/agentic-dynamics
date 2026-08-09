import * as http from "http";
import * as fs from "fs";
import * as path from "path";
import { WebSocketServer, WebSocket } from "ws";
import chokidar from "chokidar";
import { buildSite, loadConfig } from "../lib/builder";

const RELOAD_SCRIPT = `
<script>
(function() {
  var ws = new WebSocket('ws://' + location.host + '/__livereload');
  ws.onmessage = function(msg) {
    if (msg.data === 'reload') location.reload();
  };
})();
</script>
`;

function injectReloadScript(html: string): string {
  if (html.includes("</body>")) {
    return html.replace("</body>", RELOAD_SCRIPT + "\n</body>");
  }
  return html + RELOAD_SCRIPT;
}

function contentType(filePath: string): string {
  const ext = path.extname(filePath).toLowerCase();
  const types: Record<string, string> = {
    ".html": "text/html",
    ".css": "text/css",
    ".js": "application/javascript",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".svg": "image/svg+xml",
    ".xml": "application/xml",
  };
  return types[ext] || "application/octet-stream";
}

export function serve(sourceDir: string, templateDir: string, outputDir: string, port: number): void {
  let ctx = buildSite(sourceDir, templateDir, outputDir);

  const server = http.createServer((req, res) => {
    let urlPath = req.url?.split("?")[0] || "/";
    if (urlPath.endsWith("/")) urlPath += "index.html";
    if (!path.extname(urlPath)) urlPath += ".html";

    const filePath = path.join(outputDir, urlPath.replace(/^\//, ""));

    try {
      if (fs.existsSync(filePath) && fs.statSync(filePath).isFile()) {
        let content = fs.readFileSync(filePath);
        if (filePath.endsWith(".html")) {
          content = Buffer.from(injectReloadScript(content.toString("utf-8")));
        }
        res.writeHead(200, { "Content-Type": contentType(filePath) });
        res.end(content);
        return;
      }
    } catch {
      // fall through to 404
    }

    res.writeHead(404, { "Content-Type": "text/html" });
    res.end("<h1>404 Not Found</h1>");
  });

  const wss = new WebSocketServer({ server });

  const watcher = chokidar.watch([sourceDir, templateDir], {
    ignoreInitial: true,
    awaitWriteFinish: { stabilityThreshold: 200 },
  });

  function rebuild(): void {
    try {
      ctx = buildSite(sourceDir, templateDir, outputDir);
      console.log("[statick] site rebuilt");
      for (const client of wss.clients) {
        if (client.readyState === WebSocket.OPEN) {
          client.send("reload");
        }
      }
    } catch (err) {
      console.error("[statick] rebuild error:", err);
    }
  }

  watcher.on("all", () => rebuild());

  server.listen(port, () => {
    console.log(`[statick] dev server at http://localhost:${port}`);
  });
}
