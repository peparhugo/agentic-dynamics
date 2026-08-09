import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import { readFile } from "node:fs/promises";
import { join, extname } from "node:path";
import { WebSocketServer } from "ws";
import { watch } from "chokidar";
import type { SiteConfig } from "./types.js";
import { generate } from "./generator.js";

const RELOAD_SCRIPT = `
<script>
(function() {
  var ws = new WebSocket('ws://' + location.host + '/__live_reload');
  ws.onmessage = function(msg) {
    if (msg.data === 'reload') location.reload();
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

export async function serve(config: SiteConfig, watchMode: boolean): Promise<void> {
  const wss = new WebSocketServer({ noServer: true });

  wss.on("connection", (ws) => {
    ws.on("error", () => {});
  });

  function broadcast() {
    for (const client of wss.clients) {
      if (client.readyState === 1) client.send("reload");
    }
  }

  const server = createServer(async (req: IncomingMessage, res: ServerResponse) => {
    const url = req.url === "/" ? "/index.html" : req.url ?? "/index.html";
    const filePath = join(config.out, url);

    if (url === "/__live_reload") {
      return;
    }

    try {
      let content = await readFile(filePath);
      const ext = extname(filePath);

      if (ext === ".html" && watchMode) {
        content = Buffer.concat([content, Buffer.from(RELOAD_SCRIPT)]);
      }

      res.writeHead(200, { "Content-Type": MIME[ext] ?? "application/octet-stream" });
      res.end(content);
    } catch {
      if (watchMode && url.endsWith(".html")) {
        try {
          const notFound = await readFile(join(config.out, "index.html"));
          let nf = notFound;
          if (watchMode) {
            nf = Buffer.concat([nf, Buffer.from(RELOAD_SCRIPT)]);
          }
          res.writeHead(200, { "Content-Type": "text/html" });
          res.end(nf);
          return;
        } catch {}
      }
      res.writeHead(404);
      res.end("Not found");
    }
  });

  server.on("upgrade", (req, socket, head) => {
    if (req.url === "/__live_reload") {
      wss.handleUpgrade(req, socket, head, (ws) => {
        wss.emit("connection", ws, req);
      });
    } else {
      socket.destroy();
    }
  });

  if (watchMode) {
    const contentWatcher = watch([`${config.src}/**/*.md`, `${config.tmpl}/**/*.{hbs,handlebars}`], {
      ignoreInitial: true,
    });

    const onChange = async () => {
      await generate(config);
      broadcast();
    };

    let debounceTimer: ReturnType<typeof setTimeout>;
    contentWatcher.on("all", () => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(onChange, 100);
    });
  }

  server.listen(config.port, () => {
    console.log(`Server running at http://localhost:${config.port}/`);
  });
}
