import fs from 'fs';
import http from 'http';
import path from 'path';
import { AddressInfo } from 'net';
import { WebSocket, WebSocketServer } from 'ws';
import chokidar, { FSWatcher } from 'chokidar';
import { build, BuildOptions } from './ssg';

export interface ServeOptions extends BuildOptions {
  port?: number;
  host?: string;
}

export const DEFAULT_SERVE_PORT = 3000;
export const LIVE_RELOAD_PATH = '/__live_reload';

const MIME_TYPES: Record<string, string> = {
  '.html': 'text/html',
  '.htm': 'text/html',
  '.css': 'text/css',
  '.js': 'application/javascript',
  '.mjs': 'application/javascript',
  '.json': 'application/json',
  '.map': 'application/json',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.svg': 'image/svg+xml',
  '.webp': 'image/webp',
  '.ico': 'image/x-icon',
  '.txt': 'text/plain',
  '.xml': 'application/xml',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
  '.ttf': 'font/ttf',
  '.otf': 'font/otf',
  '.pdf': 'application/pdf',
  '.md': 'text/markdown',
};

function liveReloadScript(): string {
  return `\n<script>
(function () {
  var ws;
  var retries = 0;
  function connect() {
    ws = new WebSocket('ws://' + location.host + '${LIVE_RELOAD_PATH}');
    ws.onmessage = function (event) {
      if (event.data === 'reload') {
        location.reload();
      }
    };
    ws.onclose = function () {
      if (retries < 60) {
        retries += 1;
        setTimeout(connect, 500);
      }
    };
    ws.onopen = function () {
      retries = 0;
    };
  }
  connect();
})();
</script>`;
}

export function injectLiveReload(html: string): string {
  const script = liveReloadScript();
  if (/<\/body>/i.test(html)) {
    return html.replace(/<\/body>/i, `${script}\n</body>`);
  }
  if (/<\/html>/i.test(html)) {
    return html.replace(/<\/html>/i, `${script}\n</html>`);
  }
  return html + script;
}

export interface DevServer {
  server: http.Server;
  wss: WebSocketServer;
  port: number;
  watcher: FSWatcher;
  rebuild: () => void;
  close: () => Promise<void>;
}

export function startDevServer(options: ServeOptions = {}): DevServer {
  const outputDir = path.resolve(options.outputDir ?? 'dist');
  const contentDir = path.resolve(options.contentDir ?? 'content');
  const templateDir = path.resolve(options.templateDir ?? 'templates');
  const port = options.port ?? DEFAULT_SERVE_PORT;
  const host = options.host ?? '127.0.0.1';

  let rebuilding = false;
  let pending = false;

  function broadcastReload(): void {
    for (const client of wss.clients) {
      if (client.readyState === WebSocket.OPEN) {
        client.send('reload');
      }
    }
  }

  function rebuild(): void {
    if (rebuilding) {
      pending = true;
      return;
    }
    rebuilding = true;
    try {
      const pages = build({
        contentDir,
        outputDir,
        templateDir,
        defaultTemplate: options.defaultTemplate,
        defaultLayout: options.defaultLayout,
      });
      console.log(`[ssg] rebuilt ${pages.length} page(s)`);
      broadcastReload();
    } catch (err) {
      console.error('[ssg] rebuild failed:', err instanceof Error ? err.message : err);
    } finally {
      rebuilding = false;
      if (pending) {
        pending = false;
        rebuild();
      }
    }
  }

  const server = http.createServer((req, res) => {
    const requestUrl = new URL(req.url ?? '/', `http://${req.headers.host ?? 'localhost'}`);
    let pathname: string;
    try {
      pathname = decodeURIComponent(requestUrl.pathname);
    } catch {
      res.writeHead(400);
      res.end('Bad Request');
      return;
    }

    let filePath = path.join(outputDir, path.normalize(pathname));
    if (!filePath.startsWith(outputDir + path.sep)) {
      res.writeHead(403);
      res.end('Forbidden');
      return;
    }

    if (fs.existsSync(filePath) && fs.statSync(filePath).isDirectory()) {
      filePath = path.join(filePath, 'index.html');
    } else if (!path.extname(filePath) && fs.existsSync(`${filePath}.html`)) {
      filePath = `${filePath}.html`;
    }

    if (!fs.existsSync(filePath) || fs.statSync(filePath).isDirectory()) {
      res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
      res.end('Not Found');
      return;
    }

    const ext = path.extname(filePath).toLowerCase();
    const mime = MIME_TYPES[ext] ?? 'application/octet-stream';
    let body = fs.readFileSync(filePath);

    if (mime === 'text/html') {
      body = Buffer.from(injectLiveReload(body.toString('utf8')), 'utf8');
    }

    res.writeHead(200, { 'Content-Type': `${mime}; charset=utf-8` });
    res.end(body);
  });

  const wss = new WebSocketServer({ server, path: LIVE_RELOAD_PATH });

  server.listen(port, host);

  const watchPaths = [contentDir, templateDir].filter((dir) => fs.existsSync(dir));
  const watcher = chokidar.watch(watchPaths, { ignoreInitial: false });

  let rebuildTimer: ReturnType<typeof setTimeout> | null = null;
  watcher.on('all', (_event, filePath) => {
    if (filePath.startsWith(outputDir + path.sep)) {
      return;
    }
    if (rebuildTimer) {
      clearTimeout(rebuildTimer);
    }
    rebuildTimer = setTimeout(() => {
      rebuildTimer = null;
      rebuild();
    }, 50);
  });

  let boundPort = port;
  server.once('listening', () => {
    const address = server.address() as AddressInfo | null;
    if (address && typeof address === 'object') {
      boundPort = address.port;
    }
  });

  const close = async () => {
    if (rebuildTimer) {
      clearTimeout(rebuildTimer);
      rebuildTimer = null;
    }
    for (const client of wss.clients) {
      client.terminate();
    }
    wss.close();
    await watcher.close();
    await new Promise<void>((resolve, reject) => {
      server.close((err) => (err ? reject(err) : resolve()));
      server.closeIdleConnections();
    });
  };

  return {
    server,
    wss,
    get port() {
      return boundPort;
    },
    watcher,
    rebuild,
    close,
  };
}
