import * as fs from 'fs';
import * as http from 'http';
import * as net from 'net';
import * as path from 'path';
import chokidar from 'chokidar';
import { WebSocketServer, WebSocket } from 'ws';
import { build } from '../builder';
import { Plugin } from '../plugin';

export interface ServeOptions {
  contentDir: string;
  outputDir: string;
  templatesDir?: string;
  port: number;
  host?: string;
}

export interface DevServer {
  port: number;
  host: string;
  outputDir: string;
  server: http.Server;
  close(): Promise<void>;
}

export const LIVE_RELOAD_PATH = '/__ssg_live_reload';

const LIVE_RELOAD_SCRIPT = `<script>
(function () {
  var protocol = location.protocol === 'https:' ? 'wss://' : 'ws://';
  var socket = new WebSocket(protocol + location.host + '${LIVE_RELOAD_PATH}');
  socket.onmessage = function (event) {
    if (event.data === 'reload') {
      location.reload();
    }
  };
})();
</script>
`;

export function injectLiveReloadScript(html: string): string {
  const bodyClose = html.lastIndexOf('</body>');
  if (bodyClose !== -1) {
    return (
      html.slice(0, bodyClose) + LIVE_RELOAD_SCRIPT + html.slice(bodyClose)
    );
  }
  return html + LIVE_RELOAD_SCRIPT;
}

const CONTENT_TYPES: Record<string, string> = {
  '.html': 'text/html; charset=utf-8',
  '.htm': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.ico': 'image/x-icon',
  '.webp': 'image/webp',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
  '.txt': 'text/plain; charset=utf-8',
  '.md': 'text/plain; charset=utf-8',
};

function contentTypeFor(filePath: string): string {
  return CONTENT_TYPES[path.extname(filePath).toLowerCase()] ?? 'application/octet-stream';
}

function isInside(baseDir: string, target: string): boolean {
  const rel = path.relative(path.resolve(baseDir), target);
  return rel !== '' && !rel.startsWith('..') && !path.isAbsolute(rel);
}

export function createDevServer(options: ServeOptions): DevServer {
  const contentDir = path.resolve(options.contentDir);
  const outputDir = path.resolve(options.outputDir);
  const templatesDir = options.templatesDir ?? path.resolve('templates');
  const host = options.host ?? '127.0.0.1';
  const port = options.port;

  const rebuild = (): void => {
    const result = build({
      contentDir,
      outputDir,
      templatesDir,
    });
    process.stdout.write(
      `Rebuilt ${result.pages.length} page(s) to ${result.outputDir}\n`
    );
    for (const client of wss.clients) {
      if (client.readyState === WebSocket.OPEN) {
        client.send('reload');
      }
    }
  };

  const server = http.createServer((req, res) => {
    const requestUrl = (req.url ?? '/').split('?')[0];
    let decoded: string;
    try {
      decoded = decodeURIComponent(requestUrl);
    } catch {
      res.writeHead(400);
      res.end('Bad Request');
      return;
    }
    let filePath = path.join(outputDir, decoded === '/' ? 'index.html' : decoded);
    filePath = path.normalize(filePath);

    if (!isInside(outputDir, filePath)) {
      res.writeHead(403);
      res.end('Forbidden');
      return;
    }

    if (fs.existsSync(filePath) && fs.statSync(filePath).isFile()) {
      const isHtml = path.extname(filePath).toLowerCase() === '.html';
      let body = fs.readFileSync(filePath);
      if (isHtml) {
        body = Buffer.from(injectLiveReloadScript(body.toString('utf8')));
      }
      res.writeHead(200, {
        'Content-Type': contentTypeFor(filePath),
        'Content-Length': body.length,
      });
      res.end(body);
      return;
    }

    res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
    res.end('Not Found');
  });

  const wss = new WebSocketServer({ noServer: true });

  const connections = new Set<net.Socket>();
  server.on('connection', (socket) => {
    connections.add(socket);
    socket.on('close', () => {
      connections.delete(socket);
    });
  });

  server.on('upgrade', (req, socket, head) => {
    const requestUrl = (req.url ?? '').split('?')[0];
    if (requestUrl !== LIVE_RELOAD_PATH) {
      socket.destroy();
      return;
    }
    wss.handleUpgrade(req, socket, head, (ws) => {
      wss.emit('connection', ws, req);
    });
  });

  rebuild();

  const watchPaths = [contentDir, templatesDir].filter((dir) =>
    fs.existsSync(dir)
  );

  const watcher = chokidar.watch(watchPaths, {
    ignoreInitial: true,
    persistent: false,
    awaitWriteFinish: { stabilityThreshold: 100, pollInterval: 20 },
  });

  let watcherReady = watchPaths.length === 0;
  watcher.on('ready', () => {
    watcherReady = true;
  });

  let rebuildTimer: NodeJS.Timeout | null = null;
  const scheduleRebuild = (): void => {
    if (rebuildTimer) {
      clearTimeout(rebuildTimer);
    }
    rebuildTimer = setTimeout(() => {
      rebuildTimer = null;
      try {
        rebuild();
      } catch (err) {
        process.stderr.write(`Rebuild failed: ${String(err)}\n`);
      }
    }, 50);
  };

  watcher.on('add', scheduleRebuild);
  watcher.on('change', scheduleRebuild);
  watcher.on('unlink', scheduleRebuild);

  server.listen(port, host);

  return {
    port,
    host,
    outputDir,
    server,
    close: async () => {
      if (rebuildTimer) {
        clearTimeout(rebuildTimer);
        rebuildTimer = null;
      }
      if (!watcherReady) {
        await new Promise<void>((resolve) => {
          const timer = setTimeout(resolve, 1000);
          watcher.once('ready', () => {
            clearTimeout(timer);
            resolve();
          });
        });
      }
      await watcher.close();
      for (const client of wss.clients) {
        client.terminate();
      }
      await new Promise<void>((resolve) => wss.close(() => resolve()));
      for (const socket of connections) {
        socket.destroy();
      }
      await new Promise<void>((resolve) => {
        server.close(() => resolve());
        server.closeAllConnections?.();
      });
      await new Promise<void>((resolve) => setTimeout(resolve, 0));
    },
  };
}

export class DevServerPlugin implements Plugin {
  name = 'dev-server';

  private readonly options: ServeOptions;
  private devServer: DevServer | null = null;

  constructor(options: ServeOptions) {
    this.options = options;
  }

  onStart(): void {
    this.devServer = createDevServer(this.options);
  }

  onEnd(): void {
    if (this.devServer) {
      void this.devServer.close();
    }
  }

  start(): DevServer {
    this.devServer = createDevServer(this.options);
    return this.devServer;
  }
}
