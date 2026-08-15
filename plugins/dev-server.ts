import * as fs from 'fs';
import * as http from 'http';
import * as path from 'path';
import chokidar from 'chokidar';
import { WebSocket, WebSocketServer } from 'ws';
import type { Plugin, PluginContext } from '../src/plugin';
import type { Page } from '../src/types';

export interface DevServerStartOptions {
  outputDir: string;
  /** Directories to watch; a change in any of them triggers a rebuild. */
  watchPaths: string[];
  /** Port to listen on. Use 0 to let the OS assign an ephemeral port. */
  port: number;
  /** Delay (ms) between a watched file change and the triggered rebuild, to coalesce bursts of changes. */
  debounceMs: number;
  /** Invoked to rebuild the site; the resulting pages flow back through this plugin's afterBuild hook. */
  rebuild: () => void;
}

export interface DevServerHandle {
  port: number;
  url: string;
  close(): Promise<void>;
}

const LIVERELOAD_PATH = '/__livereload';

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
  '.xml': 'application/xml; charset=utf-8',
};

function liveReloadScript(): string {
  return `<script>
(function () {
  var protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  var socket = new WebSocket(protocol + '//' + window.location.host + '${LIVERELOAD_PATH}');
  socket.addEventListener('message', function (event) {
    if (event.data === 'reload') {
      window.location.reload();
    }
  });
})();
</script>`;
}

function injectLiveReload(html: string): string {
  const script = liveReloadScript();
  if (/<\/body>/i.test(html)) {
    return html.replace(/<\/body>/i, `${script}\n</body>`);
  }
  return `${html}\n${script}`;
}

/** Resolves a request path to a file within rootDir, refusing to escape it via `..` traversal. */
function resolveServablePath(rootDir: string, urlPath: string): string | undefined {
  const decoded = decodeURIComponent(urlPath.split('?')[0] ?? '/');
  let filePath = path.normalize(path.join(rootDir, decoded));

  if (filePath !== rootDir && !filePath.startsWith(rootDir + path.sep)) {
    return undefined;
  }

  if (fs.existsSync(filePath) && fs.statSync(filePath).isDirectory()) {
    filePath = path.join(filePath, 'index.html');
  }

  if (!fs.existsSync(filePath) || !fs.statSync(filePath).isFile()) {
    return undefined;
  }

  return filePath;
}

/**
 * Built-in plugin that serves the built site over HTTP with live reload.
 * As a `Plugin`, its `afterBuild` hook broadcasts a reload message to
 * connected browsers whenever a rebuild completes as part of the plugin
 * pipeline. The HTTP server, WebSocket server, and file watcher themselves
 * are a long-lived process spanning many rebuilds, so they're managed via
 * the dedicated `start()`/`close()` API below rather than the single-shot
 * `onStart`/`onEnd` hooks.
 */
export class DevServerPlugin implements Plugin {
  readonly name = 'dev-server';

  private readonly clients = new Set<WebSocket>();

  afterBuild(_pages: Page[], _ctx: PluginContext): void {
    this.broadcastReload();
  }

  private broadcastReload(): void {
    for (const client of this.clients) {
      if (client.readyState === WebSocket.OPEN) {
        client.send('reload');
      }
    }
  }

  private requestListener(outputDir: string): http.RequestListener {
    return (req, res) => {
      const filePath = resolveServablePath(outputDir, req.url ?? '/');

      if (!filePath) {
        res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
        res.end('Not found');
        return;
      }

      const ext = path.extname(filePath).toLowerCase();
      const contentType = MIME_TYPES[ext] ?? 'application/octet-stream';

      if (ext === '.html') {
        const html = fs.readFileSync(filePath, 'utf8');
        res.writeHead(200, { 'Content-Type': contentType });
        res.end(injectLiveReload(html));
        return;
      }

      res.writeHead(200, { 'Content-Type': contentType });
      fs.createReadStream(filePath).pipe(res);
    };
  }

  /** Starts the HTTP server, WebSocket server, and file watcher, resolving once both are ready. */
  start(options: DevServerStartOptions): Promise<DevServerHandle> {
    const { outputDir, watchPaths, port, debounceMs, rebuild } = options;

    const wss = new WebSocketServer({ noServer: true });
    const httpServer = http.createServer(this.requestListener(outputDir));

    httpServer.on('upgrade', (req, socket, head) => {
      if (req.url !== LIVERELOAD_PATH) {
        socket.destroy();
        return;
      }
      wss.handleUpgrade(req, socket, head, (ws) => {
        this.clients.add(ws);
        ws.on('close', () => this.clients.delete(ws));
      });
    });

    let rebuildTimer: ReturnType<typeof setTimeout> | undefined;
    const scheduleRebuild = (): void => {
      if (rebuildTimer) clearTimeout(rebuildTimer);
      rebuildTimer = setTimeout(() => {
        rebuildTimer = undefined;
        try {
          rebuild();
        } catch (err) {
          // eslint-disable-next-line no-console
          console.error('Rebuild failed:', err instanceof Error ? err.message : err);
        }
      }, debounceMs);
    };

    const watcher = chokidar.watch(watchPaths, { ignoreInitial: true });
    watcher.on('add', scheduleRebuild);
    watcher.on('change', scheduleRebuild);
    watcher.on('unlink', scheduleRebuild);

    const watcherReady = new Promise<void>((resolve) => watcher.once('ready', resolve));
    const listening = new Promise<number>((resolve, reject) => {
      httpServer.once('error', reject);
      httpServer.listen(port, () => {
        httpServer.removeListener('error', reject);
        const address = httpServer.address();
        resolve(typeof address === 'object' && address ? address.port : port);
      });
    });

    const clients = this.clients;

    return Promise.all([listening, watcherReady]).then(([boundPort]) => ({
      port: boundPort,
      url: `http://localhost:${boundPort}`,
      close(): Promise<void> {
        if (rebuildTimer) clearTimeout(rebuildTimer);
        for (const client of clients) client.terminate();
        return watcher.close().then(
          () =>
            new Promise<void>((resolveClose, rejectClose) => {
              wss.close(() => {
                httpServer.close((err) => {
                  if (err) rejectClose(err);
                  else resolveClose();
                });
              });
            })
        );
      },
    }));
  }
}
