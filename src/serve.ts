import http from 'http';
import fs from 'fs/promises';
import path from 'path';
import { AddressInfo } from 'net';
import chokidar from 'chokidar';
import { WebSocket, WebSocketServer } from 'ws';
import { buildSite } from './build';
import { DEFAULT_TEMPLATE_DIR } from './template';
import { BuildOptions } from './types';

type FileStats = Awaited<ReturnType<typeof fs.stat>>;

const DEFAULT_SERVE_HOST = 'localhost';
const DEFAULT_SERVE_PORT = 3000;
const LIVE_RELOAD_PATH = '/__ssg_ws';
const REBUILD_DEBOUNCE_MS = 100;

const MIME_TYPES: Record<string, string> = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.map': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.svg': 'image/svg+xml',
  '.webp': 'image/webp',
  '.ico': 'image/x-icon',
  '.txt': 'text/plain; charset=utf-8',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
  '.ttf': 'font/ttf',
};

export interface ServeOptions {
  contentDir: string;
  outputDir: string;
  templateDir?: string;
  port?: number;
  host?: string;
}

export interface DevServer {
  server: http.Server;
  port: number;
  host: string;
  watcher: chokidar.FSWatcher;
  wss: WebSocketServer;
  rebuild(): Promise<void>;
  close(): Promise<void>;
  onRebuild(callback: () => void): void;
}

export function liveReloadClientScript(): string {
  return `<script>
(function () {
  var scheme = location.protocol === 'https:' ? 'wss' : 'ws';
  var url = scheme + '://' + location.host + '${LIVE_RELOAD_PATH}';
  function connect() {
    var socket;
    try {
      socket = new WebSocket(url);
    } catch (err) {
      return;
    }
    socket.onmessage = function (event) {
      try {
        var message = JSON.parse(event.data);
        if (message && message.type === 'reload') {
          location.reload();
        }
      } catch (err) {}
    };
    socket.onclose = function () {
      setTimeout(connect, 1000);
    };
    socket.onerror = function () {
      socket.close();
    };
  }
  connect();
})();
</script>`;
}

export function injectLiveReloadScript(html: string): string {
  const script = liveReloadClientScript();
  const lower = html.toLowerCase();
  const bodyCloseIndex = lower.lastIndexOf('</body>');
  if (bodyCloseIndex !== -1) {
    return (
      html.slice(0, bodyCloseIndex) + `${script}\n` + html.slice(bodyCloseIndex)
    );
  }
  return html + script;
}

function contentTypeFor(filePath: string): string {
  const ext = path.extname(filePath).toLowerCase();
  return MIME_TYPES[ext] ?? 'application/octet-stream';
}

function isPathInside(root: string, target: string): boolean {
  const relative = path.relative(root, target);
  return (
    relative === '' ||
    (!relative.startsWith('..') && !path.isAbsolute(relative))
  );
}

export async function startDevServer(
  options: ServeOptions
): Promise<DevServer> {
  const contentDir = path.resolve(options.contentDir);
  const outputDir = path.resolve(options.outputDir);
  const templateDir = path.resolve(
    options.templateDir ?? DEFAULT_TEMPLATE_DIR
  );
  const host = options.host ?? DEFAULT_SERVE_HOST;
  const requestedPort = options.port ?? DEFAULT_SERVE_PORT;

  await buildSite({ contentDir, outputDir, templateDir } as BuildOptions);

  const wss = new WebSocketServer({ noServer: true });
  const rebuildCallbacks: Array<() => void> = [];
  let rebuildTimer: NodeJS.Timeout | undefined;

  function broadcastReload(): void {
    const data = JSON.stringify({ type: 'reload' });
    for (const client of wss.clients) {
      if (client.readyState === WebSocket.OPEN) {
        client.send(data);
      }
    }
  }

  async function rebuild(): Promise<void> {
    await buildSite({ contentDir, outputDir, templateDir } as BuildOptions);
    broadcastReload();
    for (const callback of rebuildCallbacks) {
      callback();
    }
  }

  function scheduleRebuild(): void {
    if (rebuildTimer) {
      clearTimeout(rebuildTimer);
    }
    rebuildTimer = setTimeout(() => {
      rebuild().catch(() => {
        // Keep serving the last good build when a rebuild fails.
      });
    }, REBUILD_DEBOUNCE_MS);
  }

  async function sendFile(
    res: http.ServerResponse,
    filePath: string,
    injectHtml: boolean
  ): Promise<void> {
    const data = await fs.readFile(filePath);
    if (injectHtml && path.extname(filePath).toLowerCase() === '.html') {
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
      res.end(injectLiveReloadScript(data.toString('utf-8')));
      return;
    }
    res.writeHead(200, { 'Content-Type': contentTypeFor(filePath) });
    res.end(data);
  }

  async function handleRequest(
    req: http.IncomingMessage,
    res: http.ServerResponse
  ): Promise<void> {
    try {
      const url = new URL(req.url ?? '/', `http://${req.headers.host ?? host}`);
      const pathname = decodeURIComponent(url.pathname);
      let filePath = path.normalize(path.join(outputDir, pathname));
      if (!isPathInside(outputDir, filePath)) {
        res.writeHead(403, { 'Content-Type': 'text/plain; charset=utf-8' });
        res.end('Forbidden');
        return;
      }

      let stats: FileStats;
      try {
        stats = await fs.stat(filePath);
      } catch {
        res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
        res.end('Not Found');
        return;
      }

      if (stats.isDirectory()) {
        filePath = path.join(filePath, 'index.html');
        try {
          await fs.stat(filePath);
        } catch {
          res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
          res.end('Not Found');
          return;
        }
      }

      await sendFile(res, filePath, true);
    } catch {
      res.writeHead(500, { 'Content-Type': 'text/plain; charset=utf-8' });
      res.end('Internal Server Error');
    }
  }

  const server = http.createServer((req, res) => {
    handleRequest(req, res).catch(() => {
      res.writeHead(500, { 'Content-Type': 'text/plain; charset=utf-8' });
      res.end('Internal Server Error');
    });
  });

  server.on('upgrade', (req, socket, head) => {
    let pathname = '/';
    try {
      pathname = new URL(req.url ?? '/', 'http://localhost').pathname;
    } catch {
      // ignore malformed upgrade requests
    }
    if (pathname === LIVE_RELOAD_PATH) {
      wss.handleUpgrade(req, socket, head, (ws) => {
        wss.emit('connection', ws, req);
      });
    } else {
      socket.destroy();
    }
  });

  const watchPaths = [contentDir, templateDir];
  const watcher = chokidar.watch(watchPaths, {
    ignoreInitial: true,
    ignorePermissionErrors: true,
  });
  watcher.on('all', (_event, filePath) => {
    if (path.resolve(filePath).startsWith(outputDir + path.sep)) {
      return;
    }
    scheduleRebuild();
  });

  await new Promise<void>((resolve, reject) => {
    server.once('error', reject);
    server.listen(requestedPort, host, () => resolve());
  });

  const address = server.address() as AddressInfo;
  const port = address.port;

  return {
    server,
    port,
    host,
    watcher,
    wss,
    rebuild,
    async close(): Promise<void> {
      if (rebuildTimer) {
        clearTimeout(rebuildTimer);
      }
      await watcher.close();
      for (const client of wss.clients) {
        client.terminate();
      }
      await new Promise<void>((resolve) => wss.close(() => resolve()));
      await new Promise<void>((resolve) => server.close(() => resolve()));
    },
    onRebuild(callback: () => void): void {
      rebuildCallbacks.push(callback);
    },
  };
}
