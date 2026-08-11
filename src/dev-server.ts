import http from "http";
import path from "path";
import { promises as fs } from "fs";
import chokidar from "chokidar";
import { WebSocketServer, WebSocket } from "ws";
import { build } from "./index";

export interface DevServerOptions {
  contentDir: string;
  outputDir: string;
  templatesDir?: string;
  port: number;
}

const MIME_TYPES: Record<string, string> = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".gif": "image/gif",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
  ".xml": "application/xml; charset=utf-8",
  ".txt": "text/plain; charset=utf-8",
};

function getMimeType(filePath: string): string {
  const ext = path.extname(filePath).toLowerCase();
  return MIME_TYPES[ext] || "application/octet-stream";
}

export function injectLiveReloadScript(html: string, port: number): string {
  const script = `<script>(function(){var ws=new WebSocket("ws://localhost:${port}/__livereload");ws.onmessage=function(m){if(m.data==="reload"){window.location.reload();}};})();</script>`;
  return html.replace("</body>", script + "</body>");
}

async function serveFile(
  filePath: string,
  res: http.ServerResponse,
  port: number
): Promise<void> {
  try {
    await fs.access(filePath);
    const stat = await fs.stat(filePath);

    if (stat.isDirectory()) {
      const indexPath = path.join(filePath, "index.html");
      try {
        await fs.access(indexPath);
        filePath = indexPath;
      } catch {
        res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
        res.end();
        return;
      }
    }

    let content = await fs.readFile(filePath);
    const ext = path.extname(filePath).toLowerCase();

    if (ext === ".html") {
      let html = content.toString("utf-8");
      html = injectLiveReloadScript(html, port);
      res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
      res.end(html, "utf-8");
    } else {
      res.writeHead(200, { "Content-Type": getMimeType(filePath) });
      res.end(content);
    }
  } catch {
    res.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
    res.end("Not Found");
  }
}

export async function startDevServer(
  options: DevServerOptions
): Promise<{ server: http.Server; wss: WebSocketServer; close: () => Promise<void> }> {
  const contentDir = path.resolve(options.contentDir);
  const outputDir = path.resolve(options.outputDir);
  const templatesDir = options.templatesDir
    ? path.resolve(options.templatesDir)
    : path.resolve("templates");
  const port = options.port;

  await build({
    contentDir,
    outputDir,
    templatesDir,
  });

  const server = http.createServer((req, res) => {
    if (!req.url) {
      res.writeHead(404);
      res.end();
      return;
    }

    const urlPath = req.url === "/" ? "/index.html" : req.url.split("?")[0];
    const filePath = path.join(outputDir, urlPath);
    serveFile(filePath, res, port);
  });

  const wss = new WebSocketServer({ server, path: "/__livereload" });

  let rebuildTimer: NodeJS.Timeout | null = null;
  const clients = new Set<WebSocket>();

  wss.on("connection", (ws) => {
    clients.add(ws);
    ws.on("close", () => {
      clients.delete(ws);
    });
  });

  async function doRebuild(): Promise<void> {
    try {
      await build({
        contentDir,
        outputDir,
        templatesDir,
      });
      for (const client of clients) {
        if (client.readyState === WebSocket.OPEN) {
          client.send("reload");
        }
      }
    } catch (err) {
      console.error("Rebuild error:", (err as Error).message);
    }
  }

  const watcher = chokidar.watch([contentDir, templatesDir], {
    ignoreInitial: true,
  });

  watcher.on("all", () => {
    if (rebuildTimer) {
      clearTimeout(rebuildTimer);
    }
    rebuildTimer = setTimeout(() => {
      rebuildTimer = null;
      doRebuild();
    }, 100);
  });

  return new Promise((resolve) => {
    server.listen(port, () => {
      console.log(`Dev server running at http://localhost:${port}/`);
      resolve({
        server,
        wss,
        close: async () => {
          await watcher.close();
          if (rebuildTimer) {
            clearTimeout(rebuildTimer);
          }
          wss.close();
          await new Promise<void>((r) => server.close(() => r()));
        },
      });
    });
  });
}
