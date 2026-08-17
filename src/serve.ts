import fs from 'fs';
import http from 'http';
import path from 'path';
import { watch, FSWatcher } from 'chokidar';
import { WebSocketServer, WebSocket } from 'ws';
import { buildSite } from './index';

export const RELOAD_MESSAGE = 'reload';

export const LIVE_RELOAD_SCRIPT = `<script>
(function () {
  var socket = new WebSocket('ws://' + window.location.host);
  socket.addEventListener('message', function (event) {
    if (event.data === '${RELOAD_MESSAGE}') {
      window.location.reload();
    }
  });
})();
</script>`;

export interface ServeOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
  port?: number;
  host?: string;
  debounce?: number;
}

export interface DevServer {
  server: http.Server;
  port: number;
  contentDir: string;
  outputDir: string;
  templatesDir: string;
  watcher: FSWatcher;
  close(): Promise<void>;
}

const CONTENT_TYPES: Record<string, string> = {
  '.html': 'text/html; charset=utf-8',
  '.htm': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.ico': 'image/x-icon',
  '.txt': 'text/plain; charset=utf-8',
  '.md': 'text/markdown; charset=utf-8',
};

export function injectLiveReloadScript(
  html: string,
  script: string = LIVE_RELOAD_SCRIPT
): string {
  if (/<\/body>/i.test(html)) {
    return html.replace(/<\/body>/i, script + '\n</body>');
  }
  return html + '\n' + script;
}

function isHtml(filePath: string): boolean {
  const ext = path.extname(filePath).toLowerCase();
  return ext === '.html' || ext === '.htm';
}

function contentTypeFor(filePath: string): string {
  const ext = path.extname(filePath).toLowerCase();
  return CONTENT_TYPES[ext] ?? 'application/octet-stream';
}

function createRequestHandler(outputDir: string): http.RequestListener {
  return (req, res) => {
    const rawPath = (req.url ?? '/').split('?')[0];
    let pathname: string;
    try {
      pathname = decodeURIComponent(rawPath);
    } catch {
      res.writeHead(400);
      res.end('Bad request');
      return;
    }

    const relative = pathname === '/' ? 'index.html' : pathname.replace(/^\/+/, '');
    const filePath = path.resolve(outputDir, relative);

    if (filePath !== outputDir && !filePath.startsWith(outputDir + path.sep)) {
      res.writeHead(403);
      res.end('Forbidden');
      return;
    }

    if (!fs.existsSync(filePath) || !fs.statSync(filePath).isFile()) {
      res.writeHead(404);
      res.end('Not found');
      return;
    }

    let body = fs.readFileSync(filePath);
    if (isHtml(filePath)) {
      body = Buffer.from(injectLiveReloadScript(body.toString('utf8')));
    }

    res.writeHead(200, { 'Content-Type': contentTypeFor(filePath) });
    res.end(body);
  };
}

function broadcast(wss: WebSocketServer, message: string): void {
  for (const client of wss.clients) {
    if (client.readyState === WebSocket.OPEN) {
      client.send(message);
    }
  }
}

/**
 * Start a live-reload development server.
 *
 * Performs an initial build, serves the generated site from outputDir over
 * HTTP, injects a WebSocket client script into HTML responses, watches the
 * content and templates directories for changes, rebuilds on change, and tells
 * connected browsers to reload when a rebuild completes.
 */
export async function startDevServer(options: ServeOptions = {}): Promise<DevServer> {
  const contentDir = path.resolve(options.contentDir ?? 'content');
  const outputDir = path.resolve(options.outputDir ?? 'dist');
  const templatesDir = path.resolve(options.templatesDir ?? 'templates');
  const host = options.host ?? '127.0.0.1';
  const port = options.port ?? 3000;
  const debounce = options.debounce ?? 100;

  buildSite({ contentDir, outputDir, templatesDir });

  const server = http.createServer(createRequestHandler(outputDir));
  const wss = new WebSocketServer({ server });

  const watcher = watch([contentDir, templatesDir], { ignoreInitial: true });
  const watcherReady = new Promise<void>((resolve) => {
    watcher.once('ready', () => resolve());
  });

  let timer: NodeJS.Timeout | null = null;
  let building = false;
  let pending = false;

  const rebuild = (): void => {
    if (building) {
      pending = true;
      return;
    }
    building = true;
    pending = false;
    try {
      buildSite({ contentDir, outputDir, templatesDir });
      broadcast(wss, RELOAD_MESSAGE);
    } catch (err) {
      console.error('Rebuild failed:', err);
    } finally {
      building = false;
      if (pending) {
        pending = false;
        scheduleRebuild();
      }
    }
  };

  const scheduleRebuild = (): void => {
    if (timer) {
      clearTimeout(timer);
    }
    timer = setTimeout(() => {
      timer = null;
      rebuild();
    }, debounce);
  };

  watcher.on('all', () => scheduleRebuild());

  await new Promise<void>((resolve, reject) => {
    server.once('error', reject);
    server.listen(port, host, () => resolve());
  });

  await watcherReady;

  const address = server.address();
  const actualPort = typeof address === 'object' && address !== null ? address.port : port;

  return {
    server,
    port: actualPort,
    contentDir,
    outputDir,
    templatesDir,
    watcher,
    close(): Promise<void> {
      return new Promise<void>((resolve) => {
        if (timer) {
          clearTimeout(timer);
          timer = null;
        }
        for (const client of wss.clients) {
          client.terminate();
        }
        watcher.close().then(() => {
          wss.close(() => {
            server.close(() => resolve());
          });
        });
      });
    },
  };
}
