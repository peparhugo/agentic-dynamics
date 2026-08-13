import * as fs from 'fs';
import * as http from 'http';
import type { AddressInfo } from 'net';
import * as path from 'path';
import { watch, FSWatcher } from 'chokidar';
import { WebSocketServer } from 'ws';
import { buildSite } from './generator';
import { BuildOptions } from './types';

export interface DevServerOptions extends BuildOptions {
  /** Port to listen on. Defaults to 3000. Pass 0 to let the OS assign a free port. */
  port?: number;
}

export interface DevServer {
  port: number;
  close(): Promise<void>;
}

const LIVE_RELOAD_PATH = '/__livereload';
const REBUILD_DEBOUNCE_MS = 100;

const MIME_TYPES: Record<string, string> = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.ico': 'image/x-icon',
  '.txt': 'text/plain; charset=utf-8',
  '.xml': 'application/xml',
};

function liveReloadScript(): string {
  return `<script>(function(){var socket=new WebSocket((location.protocol==='https:'?'wss://':'ws://')+location.host+'${LIVE_RELOAD_PATH}');socket.addEventListener('message',function(event){if(event.data==='reload'){location.reload();}});})();</script>`;
}

/**
 * Injects the live-reload client script into an HTML document, just before
 * `</body>` when present, otherwise appended to the end of the document.
 */
export function injectLiveReload(html: string): string {
  const script = liveReloadScript();
  if (html.includes('</body>')) {
    return html.replace('</body>', `${script}</body>`);
  }
  return `${html}${script}`;
}

function serveStaticFile(req: http.IncomingMessage, res: http.ServerResponse, outputDir: string): void {
  const requestUrl = new URL(req.url || '/', 'http://localhost');
  let pathname = decodeURIComponent(requestUrl.pathname);
  if (pathname.endsWith('/')) {
    pathname += 'index.html';
  }

  const resolvedRoot = path.resolve(outputDir);
  const filePath = path.resolve(resolvedRoot, `.${pathname}`);

  if (filePath !== resolvedRoot && !filePath.startsWith(resolvedRoot + path.sep)) {
    res.writeHead(403, { 'Content-Type': 'text/plain' });
    res.end('Forbidden');
    return;
  }

  fs.readFile(filePath, (err, data) => {
    if (err) {
      res.writeHead(404, { 'Content-Type': 'text/plain' });
      res.end('Not found');
      return;
    }

    const ext = path.extname(filePath).toLowerCase();
    const contentType = MIME_TYPES[ext] || 'application/octet-stream';
    res.writeHead(200, { 'Content-Type': contentType });
    res.end(ext === '.html' ? injectLiveReload(data.toString('utf-8')) : data);
  });
}

/**
 * Starts a live-reload development server: serves the built site from
 * `outputDir`, watches `contentDir`/`templatesDir` with chokidar, rebuilds
 * on change, and pushes a reload message to connected browsers over a
 * WebSocket at `/__livereload`.
 */
export async function startDevServer(options: DevServerOptions): Promise<DevServer> {
  const { contentDir, outputDir, templatesDir, port = 3000 } = options;

  buildSite({ contentDir, outputDir, templatesDir });

  const server = http.createServer((req, res) => serveStaticFile(req, res, outputDir));
  const wss = new WebSocketServer({ server, path: LIVE_RELOAD_PATH });

  function broadcastReload(): void {
    for (const client of wss.clients) {
      if (client.readyState === client.OPEN) {
        client.send('reload');
      }
    }
  }

  let rebuildTimer: NodeJS.Timeout | undefined;
  function scheduleRebuild(): void {
    if (rebuildTimer) clearTimeout(rebuildTimer);
    rebuildTimer = setTimeout(() => {
      try {
        buildSite({ contentDir, outputDir, templatesDir });
        broadcastReload();
      } catch (err) {
        // eslint-disable-next-line no-console
        console.error('Rebuild failed:', err instanceof Error ? err.message : err);
      }
    }, REBUILD_DEBOUNCE_MS);
  }

  const watchPaths = [contentDir, templatesDir].filter(
    (dir): dir is string => !!dir && fs.existsSync(dir)
  );
  const watcher: FSWatcher = watch(watchPaths, { ignoreInitial: true });
  watcher.on('add', scheduleRebuild);
  watcher.on('change', scheduleRebuild);
  watcher.on('unlink', scheduleRebuild);

  await new Promise<void>((resolve) => watcher.once('ready', () => resolve()));
  await new Promise<void>((resolve) => server.listen(port, resolve));

  const actualPort = (server.address() as AddressInfo).port;

  return {
    port: actualPort,
    async close(): Promise<void> {
      if (rebuildTimer) clearTimeout(rebuildTimer);
      for (const client of wss.clients) {
        client.terminate();
      }
      await watcher.close();
      await new Promise<void>((resolve) => wss.close(() => resolve()));
      await new Promise<void>((resolve) => server.close(() => resolve()));
    },
  };
}
