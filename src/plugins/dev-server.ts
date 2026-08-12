import http from 'http';
import fs from 'fs/promises';
import path from 'path';
import { AddressInfo } from 'net';
import chokidar from 'chokidar';
import { WebSocket, WebSocketServer } from 'ws';
import { Plugin, SsgContext } from '../plugin';
import { BuildOptions } from '../types';
import { createEngine } from '../engine';
import { loadConfiguredPlugins } from '../config';

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

export class DevServerPlugin implements Plugin {
  name = 'dev-server';

  private server: http.Server | undefined;
  private wss: WebSocketServer | undefined;
  private watcher: chokidar.FSWatcher | undefined;
  private ctx: SsgContext | undefined;
  private rebuildCallbacks: Array<() => void> = [];
  private rebuildTimer: NodeJS.Timeout | undefined;
  private port = 0;
  private host = DEFAULT_SERVE_HOST;

  constructor(private options: ServeOptions) {}

  async onStart(ctx: SsgContext): Promise<void> {
    this.ctx = ctx;
    const outputDir = path.resolve(ctx.options.outputDir);
    const host = this.options.host ?? DEFAULT_SERVE_HOST;
    const requestedPort = this.options.port ?? DEFAULT_SERVE_PORT;
    this.host = host;

    const wss = new WebSocketServer({ noServer: true });
    this.wss = wss;

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
    this.server = server;

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

    const watchPaths = [path.resolve(ctx.options.contentDir), ctx.templateDir];
    const watcher = chokidar.watch(watchPaths, {
      ignoreInitial: true,
      ignorePermissionErrors: true,
    });
    this.watcher = watcher;
    watcher.on('all', (_event, filePath) => {
      if (path.resolve(filePath).startsWith(outputDir + path.sep)) {
        return;
      }
      this.scheduleRebuild();
    });

    await new Promise<void>((resolve, reject) => {
      server.once('error', reject);
      server.listen(requestedPort, host, () => resolve());
    });

    const address = server.address() as AddressInfo;
    this.port = address.port;
  }

  afterBuild(): void {
    this.broadcastReload();
    for (const callback of this.rebuildCallbacks) {
      callback();
    }
  }

  async onEnd(): Promise<void> {
    if (this.rebuildTimer) {
      clearTimeout(this.rebuildTimer);
      this.rebuildTimer = undefined;
    }
    if (this.watcher) {
      await this.watcher.close();
      this.watcher = undefined;
    }
    if (this.wss) {
      for (const client of this.wss.clients) {
        client.terminate();
      }
      await new Promise<void>((resolve) => this.wss?.close(() => resolve()));
      this.wss = undefined;
    }
    if (this.server) {
      await new Promise<void>((resolve) => this.server?.close(() => resolve()));
      this.server = undefined;
    }
  }

  broadcastReload(): void {
    const data = JSON.stringify({ type: 'reload' });
    for (const client of this.wss?.clients ?? []) {
      if (client.readyState === WebSocket.OPEN) {
        client.send(data);
      }
    }
  }

  rebuild(): Promise<void> {
    const build = this.ctx?.engine.build();
    return build ? build.then(() => undefined) : Promise.resolve();
  }

  scheduleRebuild(): void {
    if (this.rebuildTimer) {
      clearTimeout(this.rebuildTimer);
    }
    this.rebuildTimer = setTimeout(() => {
      this.rebuild().catch(() => {
        // Keep serving the last good build when a rebuild fails.
      });
    }, REBUILD_DEBOUNCE_MS);
  }

  devServer(): DevServer {
    if (!this.server || !this.wss || !this.watcher) {
      throw new Error('DevServerPlugin has not been started');
    }
    return {
      server: this.server,
      port: this.port,
      host: this.host,
      watcher: this.watcher,
      wss: this.wss,
      rebuild: () => this.rebuild(),
      close: () => this.onEnd(),
      onRebuild: (callback: () => void) => {
        this.rebuildCallbacks.push(callback);
      },
    };
  }
}

export async function startDevServer(options: ServeOptions): Promise<DevServer> {
  const { plugins, config } = await loadConfiguredPlugins();
  const devPlugin = new DevServerPlugin(options);
  const engine = createEngine(options as BuildOptions, [...plugins, devPlugin], config);
  await engine.start();
  await engine.build();
  return devPlugin.devServer();
}
