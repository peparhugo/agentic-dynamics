import fs from 'fs';
import http from 'http';
import path from 'path';
import chokidar, { FSWatcher } from 'chokidar';
import { WebSocket, WebSocketServer } from 'ws';
import { Plugin, PluginContext } from '../src/plugin';

const DEFAULT_PORT = 3000;
const LIVE_RELOAD_PATH = '/__livereload';
const REBUILD_DEBOUNCE_MS = 100;

const CONTENT_TYPES: Record<string, string> = {
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

const LIVE_RELOAD_SCRIPT = `
<script>
(function () {
  var socket = new WebSocket('ws://' + location.host + '${LIVE_RELOAD_PATH}');
  socket.addEventListener('message', function (event) {
    if (event.data === 'reload') {
      location.reload();
    }
  });
})();
</script>
`;

function injectLiveReload(html: string): string {
  if (html.includes('</body>')) {
    return html.replace('</body>', `${LIVE_RELOAD_SCRIPT}</body>`);
  }
  return html + LIVE_RELOAD_SCRIPT;
}

function resolveRequestedFile(outputDir: string, urlPath: string): string | undefined {
  const decoded = decodeURIComponent(urlPath.split('?')[0] ?? '/');
  let relative = decoded === '/' ? '/index.html' : decoded;
  if (relative.endsWith('/')) relative += 'index.html';

  const root = path.resolve(outputDir);
  const resolved = path.resolve(root, `.${relative}`);
  if (resolved !== root && !resolved.startsWith(root + path.sep)) {
    return undefined;
  }
  return resolved;
}

function sendNotFound(res: http.ServerResponse): void {
  res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
  res.end('404 Not Found');
}

function serveFile(outputDir: string, urlPath: string, res: http.ServerResponse): void {
  const filePath = resolveRequestedFile(outputDir, urlPath);
  if (!filePath || !fs.existsSync(filePath) || !fs.statSync(filePath).isFile()) {
    sendNotFound(res);
    return;
  }

  const ext = path.extname(filePath).toLowerCase();
  const contentType = CONTENT_TYPES[ext] ?? 'application/octet-stream';

  if (ext === '.html') {
    const html = fs.readFileSync(filePath, 'utf-8');
    res.writeHead(200, { 'Content-Type': contentType });
    res.end(injectLiveReload(html));
    return;
  }

  res.writeHead(200, { 'Content-Type': contentType });
  fs.createReadStream(filePath).pipe(res);
}

export interface DevServerPluginOptions {
  port?: number;
  /** Triggers a full build pass (via the owning SSGEngine); called on every watched file change. */
  rebuild: () => void;
}

export interface DevServerPlugin extends Plugin {
  getPort(): number;
}

/**
 * Serves the output directory over HTTP, watches content/templates for
 * changes, and notifies connected browsers over WebSocket after each
 * rebuild. `afterBuild` (run by the engine for every build pass, including
 * ones triggered by this plugin's own watcher) is what broadcasts reloads.
 */
export function devServerPlugin(options: DevServerPluginOptions): DevServerPlugin {
  const { rebuild, port = DEFAULT_PORT } = options;
  let httpServer: http.Server | undefined;
  let wss: WebSocketServer | undefined;
  let watcher: FSWatcher | undefined;
  let rebuildTimer: NodeJS.Timeout | undefined;
  let actualPort = port;

  const broadcastReload = (): void => {
    if (!wss) return;
    for (const client of wss.clients) {
      if (client.readyState === WebSocket.OPEN) {
        client.send('reload');
      }
    }
  };

  const scheduleRebuild = (): void => {
    if (rebuildTimer) clearTimeout(rebuildTimer);
    rebuildTimer = setTimeout(() => {
      rebuild();
    }, REBUILD_DEBOUNCE_MS);
  };

  return {
    name: 'dev-server',

    getPort: () => actualPort,

    async onStart(ctx: PluginContext) {
      const outputDir = ctx.outputDir as string;

      httpServer = http.createServer((req, res) => {
        serveFile(outputDir, req.url ?? '/', res);
      });
      wss = new WebSocketServer({ server: httpServer, path: LIVE_RELOAD_PATH });

      watcher = chokidar.watch([ctx.contentDir, ctx.templatesDir], { ignoreInitial: true });
      watcher.on('add', scheduleRebuild);
      watcher.on('change', scheduleRebuild);
      watcher.on('unlink', scheduleRebuild);

      const listening = new Promise<number>((resolve, reject) => {
        httpServer!.once('error', reject);
        httpServer!.listen(port, () => {
          httpServer!.removeListener('error', reject);
          const address = httpServer!.address();
          resolve(typeof address === 'object' && address ? address.port : port);
        });
      });
      const watcherReady = new Promise<void>((resolve) => watcher!.once('ready', resolve));

      const [resolvedPort] = await Promise.all([listening, watcherReady]);
      actualPort = resolvedPort;
    },

    afterBuild() {
      broadcastReload();
    },

    async onEnd() {
      if (rebuildTimer) clearTimeout(rebuildTimer);
      if (watcher) await watcher.close();
      if (wss) {
        const socket = wss;
        await new Promise<void>((resolve) => socket.close(() => resolve()));
        for (const client of socket.clients) client.terminate();
      }
      if (httpServer) {
        const server = httpServer;
        await new Promise<void>((resolve, reject) => server.close((err) => (err ? reject(err) : resolve())));
      }
    },
  };
}
