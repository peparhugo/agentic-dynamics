import * as fs from 'fs';
import * as http from 'http';
import * as path from 'path';
import chokidar from 'chokidar';
import { WebSocket, WebSocketServer } from 'ws';
import { buildSite, BuildOptions } from './site';

export interface ServeOptions extends BuildOptions {
  port?: number;
}

export interface DevServer {
  url: string;
  port: number;
  close: () => Promise<void>;
}

export const LIVERELOAD_PATH = '/__livereload';

const REBUILD_DEBOUNCE_MS = 50;

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
};

function liveReloadScript(): string {
  return `
<script>
(function () {
  var socket = new WebSocket('ws://' + window.location.host + '${LIVERELOAD_PATH}');
  socket.addEventListener('message', function (event) {
    if (event.data === 'reload') {
      window.location.reload();
    }
  });
})();
</script>
`;
}

export function injectLiveReload(html: string): string {
  const script = liveReloadScript();
  if (html.includes('</body>')) {
    return html.replace('</body>', `${script}</body>`);
  }
  return `${html}${script}`;
}

function resolveFilePath(outputDir: string, urlPath: string): string {
  const decoded = decodeURIComponent(urlPath.split('?')[0] ?? '/');
  const relative = decoded.replace(/^\/+/, '') || 'index.html';

  let filePath = path.join(outputDir, relative);

  if (fs.existsSync(filePath) && fs.statSync(filePath).isDirectory()) {
    filePath = path.join(filePath, 'index.html');
  } else if (!fs.existsSync(filePath) && !path.extname(filePath)) {
    filePath = `${filePath}.html`;
  }

  return filePath;
}

function serveFile(outputDir: string, req: http.IncomingMessage, res: http.ServerResponse): void {
  const resolvedRoot = path.resolve(outputDir);
  const filePath = resolveFilePath(resolvedRoot, req.url ?? '/');
  const resolved = path.resolve(filePath);

  const isWithinRoot = resolved === resolvedRoot || resolved.startsWith(resolvedRoot + path.sep);
  if (!isWithinRoot || !fs.existsSync(resolved) || fs.statSync(resolved).isDirectory()) {
    res.statusCode = 404;
    res.end('Not found');
    return;
  }

  const ext = path.extname(resolved).toLowerCase();
  const contentType = MIME_TYPES[ext] ?? 'application/octet-stream';

  if (ext === '.html') {
    const html = fs.readFileSync(resolved, 'utf-8');
    res.setHeader('Content-Type', contentType);
    res.end(injectLiveReload(html));
    return;
  }

  res.setHeader('Content-Type', contentType);
  fs.createReadStream(resolved).pipe(res);
}

export function startDevServer(options: ServeOptions): Promise<DevServer> {
  const contentDir = path.resolve(options.contentDir);
  const outputDir = path.resolve(options.outputDir);
  const templatesDir = path.resolve(options.templatesDir ?? './templates');
  const requestedPort = options.port ?? 3000;

  const rebuild = (): void => {
    buildSite({ contentDir, outputDir, templatesDir });
  };

  rebuild();

  const httpServer = http.createServer((req, res) => serveFile(outputDir, req, res));
  const wss = new WebSocketServer({ server: httpServer, path: LIVERELOAD_PATH });

  const broadcastReload = (): void => {
    wss.clients.forEach((client) => {
      if (client.readyState === WebSocket.OPEN) {
        client.send('reload');
      }
    });
  };

  let rebuildTimer: ReturnType<typeof setTimeout> | null = null;
  const scheduleRebuild = (): void => {
    if (rebuildTimer) clearTimeout(rebuildTimer);
    rebuildTimer = setTimeout(() => {
      rebuildTimer = null;
      try {
        rebuild();
        broadcastReload();
      } catch (err) {
        // eslint-disable-next-line no-console
        console.error('Rebuild failed:', err instanceof Error ? err.message : err);
      }
    }, REBUILD_DEBOUNCE_MS);
  };

  const watcher = chokidar.watch([contentDir, templatesDir], { ignoreInitial: true });
  watcher.on('all', scheduleRebuild);

  const watcherReady = new Promise<void>((resolveReady) => watcher.once('ready', () => resolveReady()));

  const listening = new Promise<number>((resolve, reject) => {
    httpServer.once('error', reject);
    httpServer.listen(requestedPort, () => {
      const address = httpServer.address();
      const actualPort = typeof address === 'object' && address ? address.port : requestedPort;
      resolve(actualPort);
    });
  });

  return Promise.all([listening, watcherReady]).then(([actualPort]) => ({
    url: `http://localhost:${actualPort}`,
    port: actualPort,
    close: () =>
      new Promise<void>((resolveClose) => {
        if (rebuildTimer) clearTimeout(rebuildTimer);
        watcher.close().then(() => {
          wss.close(() => {
            httpServer.close(() => resolveClose());
          });
        });
      }),
  }));
}
