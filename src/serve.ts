import * as fs from 'fs';
import * as http from 'http';
import * as path from 'path';
import chokidar, { FSWatcher } from 'chokidar';
import { WebSocket, WebSocketServer } from 'ws';
import { build } from './build';
import { BuildOptions } from './types';

const LIVE_RELOAD_PATH = '/__livereload';
const REBUILD_DEBOUNCE_MS = 100;

const LIVE_RELOAD_SCRIPT = `<script>
(function () {
  var socket = new WebSocket('ws://' + location.host + '${LIVE_RELOAD_PATH}');
  socket.addEventListener('message', function (event) {
    if (event.data === 'reload') location.reload();
  });
})();
</script>`;

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

export interface ServeOptions extends BuildOptions {
  /** Port to listen on. Defaults to 3000. */
  port?: number;
}

export interface ServeHandle {
  port: number;
  /** Resolves once the file watcher has finished its initial scan and is actively watching for changes. */
  ready(): Promise<void>;
  close(): Promise<void>;
}

/** Inserts the live-reload client script just before `</body>`, or appends it if no closing body tag is present. */
export function injectLiveReload(html: string): string {
  if (/<\/body>/i.test(html)) {
    return html.replace(/<\/body>/i, `${LIVE_RELOAD_SCRIPT}</body>`);
  }
  return html + LIVE_RELOAD_SCRIPT;
}

/** Resolves a request URL to a file inside outputDir, rejecting attempts to escape it. Returns null if unsafe. */
function resolveFilePath(outputDir: string, requestUrl: string): string | null {
  const decoded = decodeURIComponent(requestUrl.split('?')[0].split('#')[0]);
  const resolvedOutput = path.resolve(outputDir);
  const candidate = path.resolve(resolvedOutput, `.${decoded}`);
  if (candidate !== resolvedOutput && !candidate.startsWith(resolvedOutput + path.sep)) {
    return null;
  }
  return candidate;
}

/** Finds the file to serve for a resolved path, trying directory index and .html fallbacks. */
function findServableFile(filePath: string): string | null {
  if (fs.existsSync(filePath) && fs.statSync(filePath).isDirectory()) {
    filePath = path.join(filePath, 'index.html');
  }
  if (fs.existsSync(filePath) && fs.statSync(filePath).isFile()) {
    return filePath;
  }
  const withHtml = `${filePath}.html`;
  if (fs.existsSync(withHtml) && fs.statSync(withHtml).isFile()) {
    return withHtml;
  }
  return null;
}

function handleRequest(req: http.IncomingMessage, res: http.ServerResponse, outputDir: string): void {
  const requestUrl = req.url ?? '/';
  const resolved = resolveFilePath(outputDir, requestUrl);
  const filePath = resolved ? findServableFile(resolved) : null;

  if (!filePath) {
    res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
    res.end('Not found');
    return;
  }

  const ext = path.extname(filePath).toLowerCase();
  const contentType = MIME_TYPES[ext] ?? 'application/octet-stream';

  if (ext === '.html') {
    const html = fs.readFileSync(filePath, 'utf-8');
    res.writeHead(200, { 'Content-Type': contentType });
    res.end(injectLiveReload(html));
    return;
  }

  res.writeHead(200, { 'Content-Type': contentType });
  res.end(fs.readFileSync(filePath));
}

/** Starts a live-reload dev server: serves outputDir over HTTP, rebuilds on content/template changes, and pushes reloads over WebSocket. */
export function serve(options: ServeOptions): ServeHandle {
  const { contentDir, outputDir, templatesDir, siteTitle } = options;
  const port = options.port ?? 3000;

  const runBuild = (): void => {
    build({ contentDir, outputDir, templatesDir, siteTitle });
  };

  runBuild();

  const wss = new WebSocketServer({ noServer: true });

  const server = http.createServer((req, res) => handleRequest(req, res, outputDir));

  server.on('upgrade', (req, socket, head) => {
    if (req.url === LIVE_RELOAD_PATH) {
      wss.handleUpgrade(req, socket, head, (ws) => wss.emit('connection', ws, req));
    } else {
      socket.destroy();
    }
  });

  function broadcastReload(): void {
    for (const client of wss.clients) {
      if (client.readyState === WebSocket.OPEN) {
        client.send('reload');
      }
    }
  }

  let rebuildTimer: NodeJS.Timeout | undefined;
  function scheduleRebuild(): void {
    if (rebuildTimer) clearTimeout(rebuildTimer);
    rebuildTimer = setTimeout(() => {
      try {
        runBuild();
        broadcastReload();
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        // eslint-disable-next-line no-console
        console.error(`ssg: rebuild failed: ${message}`);
      }
    }, REBUILD_DEBOUNCE_MS);
  }

  const watchPaths = Array.from(new Set([contentDir, templatesDir ?? './templates'])).filter((dir) =>
    fs.existsSync(dir)
  );
  const watcher: FSWatcher = chokidar.watch(watchPaths, { ignoreInitial: true });
  watcher.on('all', () => scheduleRebuild());
  const watcherReady = new Promise<void>((resolve) => watcher.once('ready', resolve));

  server.listen(port);

  return {
    get port(): number {
      const address = server.address();
      return typeof address === 'object' && address !== null ? address.port : port;
    },
    ready(): Promise<void> {
      return watcherReady;
    },
    close(): Promise<void> {
      if (rebuildTimer) clearTimeout(rebuildTimer);
      for (const client of wss.clients) {
        client.terminate();
      }
      return watcher.close().then(
        () =>
          new Promise((resolve, reject) => {
            wss.close(() => {
              server.closeAllConnections();
              server.close((error) => (error ? reject(error) : resolve()));
            });
          })
      );
    },
  };
}
