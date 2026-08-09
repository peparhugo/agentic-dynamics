import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import chokidar from 'chokidar';
import { WebSocketServer, WebSocket } from 'ws';
import { buildSite } from './build.js';
import type { SiteConfig } from './types.js';

const MIME: Record<string, string> = {
  '.html': 'text/html; charset=utf-8',
  '.xml': 'application/xml; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.txt': 'text/plain; charset=utf-8',
};

export function reloadScript(port: number): string {
  return `<script>
(function () {
  var ws = new WebSocket('ws://' + location.hostname + ':${port}');
  ws.onmessage = function (ev) { if (ev.data === 'reload') location.reload(); };
  ws.onclose = function () { setTimeout(function () { location.reload(); }, 1000); };
})();
</script>`;
}

export interface DevServer {
  port: number;
  close(): Promise<void>;
}

/**
 * Dev server: builds the site (with live-reload script injected), serves the
 * output directory, watches source + template dirs with chokidar, rebuilds on
 * change, and broadcasts "reload" to connected WebSocket clients.
 */
export async function startDevServer(config: SiteConfig, port = 3000): Promise<DevServer> {
  const build = () => buildSite(config, { injectReloadScript: reloadScript(port) });
  build();

  const server = http.createServer((req, res) => {
    const urlPath = decodeURIComponent((req.url ?? '/').split('?')[0]);
    let filePath = path.join(config.out, urlPath);
    // Prevent path traversal
    if (!path.resolve(filePath).startsWith(path.resolve(config.out))) {
      res.writeHead(403).end('Forbidden');
      return;
    }
    if (fs.existsSync(filePath) && fs.statSync(filePath).isDirectory()) {
      filePath = path.join(filePath, 'index.html');
    }
    if (!fs.existsSync(filePath)) {
      res.writeHead(404, { 'Content-Type': 'text/html; charset=utf-8' });
      res.end(`<h1>404 Not Found</h1><p>${urlPath}</p>${reloadScript(port)}`);
      return;
    }
    res.writeHead(200, { 'Content-Type': MIME[path.extname(filePath)] ?? 'application/octet-stream' });
    res.end(fs.readFileSync(filePath));
  });

  const wss = new WebSocketServer({ server });
  const broadcast = (msg: string) => {
    for (const client of wss.clients) {
      if (client.readyState === WebSocket.OPEN) client.send(msg);
    }
  };

  const watcher = chokidar.watch([config.source, config.templates], {
    ignoreInitial: true,
    awaitWriteFinish: { stabilityThreshold: 50, pollInterval: 10 },
  });
  let rebuildTimer: NodeJS.Timeout | undefined;
  watcher.on('all', (event, file) => {
    clearTimeout(rebuildTimer);
    rebuildTimer = setTimeout(() => {
      try {
        build();
        console.log(`[ssg] rebuilt (${event}: ${file})`);
        broadcast('reload');
      } catch (err) {
        console.error(`[ssg] rebuild failed: ${(err as Error).message}`);
      }
    }, 50);
  });

  await new Promise<void>((resolve) => server.listen(port, resolve));
  const actualPort = (server.address() as { port: number }).port;
  console.log(`[ssg] dev server running at http://localhost:${actualPort}`);

  return {
    port: actualPort,
    async close() {
      clearTimeout(rebuildTimer);
      await watcher.close();
      await new Promise<void>((resolve, reject) =>
        wss.close((e) => (e ? reject(e) : resolve())),
      );
      await new Promise<void>((resolve, reject) =>
        server.close((e) => (e ? reject(e) : resolve())),
      );
    },
  };
}
