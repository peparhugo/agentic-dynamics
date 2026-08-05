import http from "node:http";
import fs from "node:fs/promises";
import path from "node:path";
import chokidar from "chokidar";
import { WebSocketServer, WebSocket } from "ws";
import { buildSite } from "./build.js";
import type { BuildOptions } from "./types.js";

export const LIVE_RELOAD_PATH = "/__livereload";

export const RELOAD_SNIPPET = `<script>
(() => {
  const connect = () => {
    const ws = new WebSocket((location.protocol === "https:" ? "wss://" : "ws://") + location.host + "${LIVE_RELOAD_PATH}");
    ws.onmessage = (e) => { if (e.data === "reload") location.reload(); };
    ws.onclose = () => setTimeout(connect, 1000);
  };
  connect();
})();
</script>`;

const MIME: Record<string, string> = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json",
  ".xml": "application/xml; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".gif": "image/gif",
  ".ico": "image/x-icon",
  ".txt": "text/plain; charset=utf-8",
  ".woff2": "font/woff2",
};

/** Inject the live-reload script before </body> (or append if absent). */
export function injectReloadScript(html: string): string {
  if (html.includes("</body>")) {
    return html.replace("</body>", `${RELOAD_SNIPPET}\n</body>`);
  }
  return html + RELOAD_SNIPPET;
}

async function resolveFile(outDir: string, urlPath: string): Promise<string | null> {
  const safe = path.normalize(decodeURIComponent(urlPath)).replace(/^(\.\.[/\\])+/, "");
  let file = path.join(outDir, safe);
  if (!file.startsWith(path.resolve(outDir) + path.sep) && file !== path.resolve(outDir)) {
    return null;
  }
  try {
    const stat = await fs.stat(file);
    if (stat.isDirectory()) file = path.join(file, "index.html");
    await fs.access(file);
    return file;
  } catch {
    return null;
  }
}

export interface DevServer {
  port: number;
  close: () => Promise<void>;
}

/** Start a dev server: initial build, static serving with reload injection, watch + rebuild. */
export async function serve(
  options: BuildOptions & { port?: number }
): Promise<DevServer> {
  const outDir = path.resolve(options.outDir);
  await buildSite(options);

  const server = http.createServer(async (req, res) => {
    const urlPath = (req.url ?? "/").split("?")[0] ?? "/";
    const file = await resolveFile(outDir, urlPath);
    if (!file) {
      res.writeHead(404, { "content-type": "text/html; charset=utf-8" });
      res.end(injectReloadScript("<h1>404 Not Found</h1>"));
      return;
    }
    const ext = path.extname(file).toLowerCase();
    const type = MIME[ext] ?? "application/octet-stream";
    if (ext === ".html") {
      const html = await fs.readFile(file, "utf8");
      res.writeHead(200, { "content-type": type });
      res.end(injectReloadScript(html));
    } else {
      res.writeHead(200, { "content-type": type });
      res.end(await fs.readFile(file));
    }
  });

  const wss = new WebSocketServer({ server, path: LIVE_RELOAD_PATH });
  const broadcast = (msg: string) => {
    for (const client of wss.clients) {
      if (client.readyState === WebSocket.OPEN) client.send(msg);
    }
  };

  let rebuildTimer: NodeJS.Timeout | null = null;
  const watcher = chokidar.watch([options.sourceDir, options.templateDir], {
    ignoreInitial: true,
  });
  watcher.on("all", (event, file) => {
    if (rebuildTimer) clearTimeout(rebuildTimer);
    rebuildTimer = setTimeout(async () => {
      try {
        console.log(`[statik] ${event}: ${file} — rebuilding...`);
        await buildSite(options);
        broadcast("reload");
      } catch (err) {
        console.error("[statik] rebuild failed:", err);
      }
    }, 100);
  });

  const port = await new Promise<number>((resolve, reject) => {
    server.once("error", reject);
    server.listen(options.port ?? 4000, () => {
      const addr = server.address();
      resolve(typeof addr === "object" && addr ? addr.port : (options.port ?? 4000));
    });
  });

  console.log(`[statik] dev server: http://localhost:${port}`);

  return {
    port,
    close: async () => {
      if (rebuildTimer) clearTimeout(rebuildTimer);
      await watcher.close();
      wss.close();
      await new Promise<void>((resolve) => server.close(() => resolve()));
    },
  };
}
