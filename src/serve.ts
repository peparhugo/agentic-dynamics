import http from 'http';
import fs from 'fs';
import path from 'path';
import chokidar, { FSWatcher } from 'chokidar';
import { WebSocketServer, WebSocket } from 'ws';
import { buildSite } from './build';

export interface DevServerOptions {
  contentDir: string;
  outputDir: string;
  templatesDir?: string;
  host?: string;
  port?: number;
}

export interface DevServer {
  server: http.Server;
  wss: WebSocketServer;
  watcher: FSWatcher;
  ready: Promise<void>;
  close(): Promise<void>;
}

const REBUILD_DEBOUNCE_MS = 100;

const MIME_TYPES: Record<string, string> = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.mjs': 'application/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.map': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.svg': 'image/svg+xml',
  '.webp': 'image/webp',
  '.ico': 'image/x-icon',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
  '.txt': 'text/plain; charset=utf-8',
};

export function liveReloadScript(): string {
  return `<script>
(function () {
  var scheme = location.protocol === 'https:' ? 'wss:' : 'ws:';
  var socket = new WebSocket(scheme + '//' + location.host);
  socket.addEventListener('message', function (event) {
    var data;
    try {
      data = JSON.parse(event.data);
    } catch (err) {
      return;
    }
    if (data && data.type === 'reload') {
      location.reload();
    }
  });
  socket.addEventListener('close', function () {
    setTimeout(function () {
      location.reload();
    }, 2000);
  });
})();
</script>`;
}

export function injectLiveReload(html: string): string {
  const script = liveReloadScript();
  const idx = html.lastIndexOf('</body>');
  if (idx === -1) {
    return html + script;
  }
  return html.slice(0, idx) + script + html.slice(idx);
}

function createHandler(outputDir: string): http.RequestListener {
  const root = path.resolve(outputDir);
  return (req, res) => {
    const urlPath = (req.url ?? '/').split('?')[0];
    const rel = urlPath === '/' ? 'index.html' : urlPath.replace(/^\/+/, '');
    const filePath = path.resolve(root, rel);

    if (filePath !== root && !filePath.startsWith(root + path.sep)) {
      res.writeHead(403, { 'Content-Type': 'text/plain; charset=utf-8' });
      res.end('Forbidden');
      return;
    }

    fs.readFile(filePath, (err, data) => {
      if (err) {
        res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
        res.end('Not Found');
        return;
      }
      const type = MIME_TYPES[path.extname(filePath).toLowerCase()] ?? 'application/octet-stream';
      const body = filePath.endsWith('.html')
        ? injectLiveReload(data.toString('utf-8'))
        : data;
      res.writeHead(200, { 'Content-Type': type, 'Cache-Control': 'no-cache' });
      res.end(body);
    });
  };
}

export function startDevServer(options: DevServerOptions): DevServer {
  const contentDir = options.contentDir;
  const outputDir = options.outputDir;
  const templatesDir = options.templatesDir;
  const host = options.host ?? 'localhost';
  const port = options.port ?? 3000;

  const server = http.createServer(createHandler(outputDir));
  const wss = new WebSocketServer({ server });
  let timer: NodeJS.Timeout | null = null;
  let closed = false;
  let watcher: FSWatcher;

  const broadcast = (message: unknown): void => {
    const payload = JSON.stringify(message);
    for (const client of wss.clients) {
      if (client.readyState === WebSocket.OPEN) {
        client.send(payload);
      }
    }
  };

  const rebuild = (): void => {
    if (closed) return;
    try {
      const pages = buildSite({ contentDir, outputDir, templatesDir });
      broadcast({ type: 'reload', timestamp: Date.now() });
      console.log(`Rebuilt ${pages.length} page${pages.length === 1 ? '' : 's'}`);
    } catch (err) {
      console.error(`Build failed: ${(err as Error).message}`);
    }
  };

  try {
    const pages = buildSite({ contentDir, outputDir, templatesDir });
    console.log(`Built ${pages.length} page${pages.length === 1 ? '' : 's'} into ${outputDir}`);
  } catch (err) {
    console.error(`Initial build failed: ${(err as Error).message}`);
  }

  const watchDirs: string[] = templatesDir ? [contentDir, templatesDir] : [contentDir];
  watcher = chokidar.watch(watchDirs, { ignoreInitial: true });

  const ready = new Promise<void>((resolve) => watcher.on('ready', () => resolve()));

  const schedule = (): void => {
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => {
      timer = null;
      rebuild();
    }, REBUILD_DEBOUNCE_MS);
  };

  watcher
    .on('add', schedule)
    .on('change', schedule)
    .on('unlink', schedule)
    .on('addDir', schedule)
    .on('unlinkDir', schedule);

  server.listen(port, host);

  const close = async (): Promise<void> => {
    closed = true;
    if (timer) {
      clearTimeout(timer);
      timer = null;
    }
    await watcher.close();
    for (const client of wss.clients) {
      client.close();
    }
    await new Promise<void>((resolve) => wss.close(() => resolve()));
    await new Promise<void>((resolve) => server.close(() => resolve()));
  };

  return { server, wss, watcher, ready, close };
}
