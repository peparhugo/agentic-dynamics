import http from 'node:http';
import { promises as fs } from 'node:fs';
import path from 'node:path';
import chokidar from 'chokidar';
import { WebSocketServer, WebSocket } from 'ws';
import { build } from './build.js';
import type { SiteConfig } from './types.js';

const MIME: Record<string, string> = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json',
  '.xml': 'application/xml; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.txt': 'text/plain; charset=utf-8',
  '.woff2': 'font/woff2',
};

export const LIVE_RELOAD_PATH = '/__livereload';

export function liveReloadScript(): string {
  return `<script>(() => {
  const connect = () => {
    const ws = new WebSocket((location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '${LIVE_RELOAD_PATH}');
    ws.onmessage = (e) => { if (e.data === 'reload') location.reload(); };
    ws.onclose = () => setTimeout(connect, 1000);
  };
  connect();
})();</script>`;
}

/** Resolve a request URL to a file within root, guarding against path traversal. */
export async function resolveFile(root: string, urlPath: string): Promise<string | null> {
  const decoded = decodeURIComponent(urlPath.split('?')[0]);
  const safe = path.normalize(decoded).replace(/^(\.\.[/\\])+/, '');
  let filePath = path.join(root, safe);
  if (!filePath.startsWith(path.resolve(root))) return null;
  try {
    const stat = await fs.stat(filePath);
    if (stat.isDirectory()) filePath = path.join(filePath, 'index.html');
    await fs.access(filePath);
    return filePath;
  } catch {
    return null;
  }
}

export interface DevServer {
  close(): Promise<void>;
  port: number;
}

export async function serve(config: SiteConfig): Promise<DevServer> {
  const inject = liveReloadScript();
  const doBuild = async () => {
    try {
      await build(config, { injectHtml: inject });
      console.log(`[sitegen] built ${new Date().toLocaleTimeString()}`);
    } catch (err) {
      console.error('[sitegen] build failed:', err instanceof Error ? err.message : err);
    }
  };
  await doBuild();

  const server = http.createServer(async (req, res) => {
    const filePath = await resolveFile(config.outDir, req.url ?? '/');
    if (!filePath) {
      res.writeHead(404, { 'Content-Type': 'text/html; charset=utf-8' });
      res.end('<h1>404 Not Found</h1>');
      return;
    }
    const type = MIME[path.extname(filePath).toLowerCase()] ?? 'application/octet-stream';
    res.writeHead(200, { 'Content-Type': type });
    res.end(await fs.readFile(filePath));
  });

  const wss = new WebSocketServer({ server, path: LIVE_RELOAD_PATH });
  const broadcast = () => {
    for (const client of wss.clients) {
      if (client.readyState === WebSocket.OPEN) client.send('reload');
    }
  };

  let timer: NodeJS.Timeout | null = null;
  const watcher = chokidar.watch([config.sourceDir, config.templateDir], {
    ignoreInitial: true,
  });
  watcher.on('all', () => {
    // Debounce bursts of file events into a single rebuild + reload.
    if (timer) clearTimeout(timer);
    timer = setTimeout(async () => {
      await doBuild();
      broadcast();
    }, 100);
  });

  await new Promise<void>((resolve) => server.listen(config.port, resolve));
  const address = server.address();
  const port = typeof address === 'object' && address ? address.port : config.port;
  console.log(`[sitegen] serving ${config.outDir} at http://localhost:${port} (live reload on)`);

  return {
    port,
    async close() {
      if (timer) clearTimeout(timer);
      await watcher.close();
      wss.close();
      await new Promise<void>((resolve, reject) =>
        server.close((err) => (err ? reject(err) : resolve())),
      );
    },
  };
}
