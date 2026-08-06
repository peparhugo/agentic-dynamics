import * as http from "http";
import * as fs from "fs";
import * as path from "path";
import { WebSocketServer, WebSocket } from "ws";
import { watch } from "chokidar";
import { SiteConfig } from "./types";
import { build } from "./build";

const RELOAD_SCRIPT = `
<script>
  (function() {
    var ws = new WebSocket('ws://' + location.host + '/__livereload');
    ws.onmessage = function(msg) {
      if (msg.data === 'reload') {
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

const MIME_TYPES: Record<string, string> = {
  ".html": "text/html",
  ".css": "text/css",
  ".js": "text/javascript",
  ".json": "application/json",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".gif": "image/gif",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
  ".xml": "application/xml",
  ".txt": "text/plain",
};

export async function startDevServer(config: SiteConfig): Promise<http.Server> {
  await build(config);

  const server = http.createServer((req, res) => {
    const url = req.url || "/";
    let filePath = path.join(config.outputDir, url === "/" ? "index.html" : url);

    if (!path.extname(filePath)) {
      filePath += ".html";
    }

    fs.readFile(filePath, (err, data) => {
      if (err) {
        res.writeHead(404, { "Content-Type": "text/plain" });
        res.end("Not Found");
        return;
      }

      const ext = path.extname(filePath);
      const contentType = MIME_TYPES[ext] || "application/octet-stream";

      if (ext === ".html") {
        const html = data.toString();
        const injected = html.replace("</body>", `${RELOAD_SCRIPT}</body>`);
        res.writeHead(200, { "Content-Type": contentType });
        res.end(injected);
      } else {
        res.writeHead(200, { "Content-Type": contentType });
        res.end(data);
      }
    });
  });

  const wss = new WebSocketServer({ server });

  wss.on("connection", (ws: WebSocket) => {
    ws.on("error", () => {});
  });

  function reload() {
    for (const client of wss.clients) {
      if (client.readyState === WebSocket.OPEN) {
        client.send("reload");
      }
    }
  }

  const watcher = watch([
    path.join(config.sourceDir, "**", "*.md"),
    path.join(config.templateDir, "**", "*.hbs"),
    path.join(config.templateDir, "**", "*.handlebars"),
  ]);

  let rebuilding = false;

  watcher.on("change", async () => {
    if (rebuilding) return;
    rebuilding = true;
    try {
      await build(config);
      reload();
    } finally {
      rebuilding = false;
    }
  });

  watcher.on("error", () => {});

  return new Promise((resolve) => {
    server.listen(config.port, () => {
      resolve(server);
    });
  });
}
