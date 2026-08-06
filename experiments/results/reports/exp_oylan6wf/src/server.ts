import http from 'node:http';
import { promises as fs } from 'node:fs';
import path from 'node:path';
import chokidar from 'chokidar';
import { WebSocketServer, WebSocket } from 'ws';
import { buildSite } from './build.js';
import type { SiteConfig } from './types.js';

const MIME: Record<string, string> = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json',
  '.xml': 'application/xml',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.webp': 'image/webp',
  '.ico': 'image/x-icon',
  '.txt': 'text/plain; charset=utf-8',
  '.woff2': 'font/woff2',
};

/** Client-side snippet injected into every HTML page served in dev mode. */
export function reloadScript(port: number): string {
  return `<script>
(() => {
  const connect = () => {
    const ws = new WebSocket("ws://" + location.hostname + ":${port}");
    ws.onmessage = (e) => { if (e.data === "reload") location.reload(); };
    ws.onclose = () => setTimeout(connect, 1000);
  };
  connect();
})();
</script>`;
}

/** Insert the reload script before </body>, or append if absent. */
export function injectReloadScript(html: string, port: number): string {
  const script = reloadScript(port);
  const idx = html.lastIndexOf('</body>');
  return idx === -1 ? html + script : html.slice(0, idx) + script + html.slice(idx);
}

export interface DevServer {
  close: () => Promise<void>;
  port: number;
}

/**
 * Dev server: serves the output dir, rebuilds on source/template changes
 * (via chokidar), and pushes "reload" to connected WebSocket clients.
 */
export async function startDevServer(
  config: SiteConfig,
  port = 3000,
  log: (msg: string) => void = console.log,
): Promise<DevServer> {
  await buildSite(config);
  const root = path.resolve(config.outDir);

  const server = http.createServer(async (req, res) => {
    try {
      const urlPath = decodeURIComponent((req.url ?? '/').split('?')[0]);
      let filePath = path.normalize(path.join(root, urlPath));
      if (!filePath.startsWith(root)) {
        res.writeHead(403).end('Forbidden');
        return;
      }
      const stat = await fs.stat(filePath).catch(() => null);
      if (stat?.isDirectory()) filePath = path.join(filePath, 'index.html');
      let data: Buffer;
      try {
        data = await fs.readFile(filePath);
      } catch {
        res.writeHead(404, { 'Content-Type': 'text/html' });
        res.end('<h1>404 Not Found</h1>');
        return;
      }
      const ext = path.extname(filePath).toLowerCase();
      const mime = MIME[ext] ?? 'application/octet-stream';
      if (ext === '.html') {
        const html = injectReloadScript(data.toString('utf8'), port);
        res.writeHead(200, { 'Content-Type': mime });
        res.end(html);
      } else {
        res.writeHead(200, { 'Content-Type': mime });
        res.end(data);
      }
    } catch (err) {
      res.writeHead(500).end(String(err));
    }
  });

  const wss = new WebSocketServer({ server });
  const broadcast = (msg: string) => {
    for (const client of wss.clients) {
      if (client.readyState === WebSocket.OPEN) client.send(msg);
    }
  };

  let rebuildTimer: NodeJS.Timeout | null = null;
  const watcher = chokidar.watch([config.sourceDir, config.templateDir], {
    ignoreInitial: true,
  });
  watcher.on('all', (event, file) => {
    if (rebuildTimer) clearTimeout(rebuildTimer);
    rebuildTimer = setTimeout(async () => {
      log(`[sprout] ${event}: ${file} — rebuilding`);
      try {
        await buildSite(config);
        broadcast('reload');
      } catch (err) {
        log(`[sprout] build failed: ${err}`);
      }
    }, 80);
  });

  await new Promise<void>((resolve) => server.listen(port, resolve));
  log(`[sprout] dev server: http://localhost:${port} (live reload enabled)`);

  return {
    port,
    close: async () => {
      await watcher.close();
      wss.close();
      await new Promise<void>((resolve, reject) =>
        server.close((e) => (e ? reject(e) : resolve())),
      );
    },
  };
}
