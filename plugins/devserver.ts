import { createServer, Server } from 'http';
import { promises as fs } from 'fs';
import * as path from 'path';
import chokidar, { FSWatcher } from 'chokidar';
import { WebSocketServer, WebSocket } from 'ws';
import { Plugin, PluginContext } from '../src/plugin';
import { injectReloadScript, LIVERELOAD_PATH } from '../src/livereload';
import type { ServeOptions, DevServer } from '../src/serve';

const DEFAULT_PORT = 3000;
const REBUILD_DEBOUNCE_MS = 100;
const WATCHER_SETTLE_MS = 250;

const MIME_TYPES: Record<string, string> = {
  '.html': 'text/html; charset=utf-8',
  '.htm': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.xml': 'application/xml; charset=utf-8',
  '.txt': 'text/plain; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.webp': 'image/webp',
  '.ico': 'image/x-icon',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
  '.ttf': 'font/ttf',
  '.pdf': 'application/pdf',
  '.map': 'application/json',
};

function resolveFilePath(urlPath: string, outputDir: string): string | null {
  let pathname: string;
  try {
    pathname = decodeURIComponent(urlPath.split('?')[0]).split('#')[0];
  } catch {
    return null;
  }
  const root = path.resolve(outputDir);
  const clean = pathname.replace(/^\/+/, '');
  const candidate = path.resolve(root, clean);
  if (candidate !== root && !candidate.startsWith(root + path.sep)) {
    return null;
  }
  return candidate;
}

async function fileStat(target: string): Promise<{ isDirectory: boolean } | null> {
  try {
    const stat = await fs.stat(target);
    return { isDirectory: stat.isDirectory() };
  } catch {
    return null;
  }
}

async function serveFile(
  reqUrl: string,
  outputDir: string,
  res: import('http').ServerResponse
): Promise<void> {
  const file = resolveFilePath(reqUrl, outputDir);
  if (!file) {
    res.writeHead(403, { 'Content-Type': 'text/plain; charset=utf-8' });
    res.end('Forbidden');
    return;
  }

  let target = file;
  let stat = await fileStat(target);
  if (stat && stat.isDirectory) {
    target = path.join(target, 'index.html');
    stat = await fileStat(target);
  }
  if (!stat) {
    res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
    res.end('Not Found');
    return;
  }

  const ext = path.extname(target).toLowerCase();
  const data = await fs.readFile(target);
  if (ext === '.html') {
    const body = data.toString('utf8');
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    res.end(injectReloadScript(body));
    return;
  }
  res.writeHead(200, { 'Content-Type': MIME_TYPES[ext] ?? 'application/octet-stream' });
  res.end(data);
}

/**
 * Built-in plugin implementing the live-reload development server.
 *
 * During `onStart` it performs an initial build, starts an HTTP server that
 * serves the built site, and watches the content and template directories. On
 * change it rebuilds through the core engine and tells connected browsers to
 * reload.
 */
export class DevServerPlugin implements Plugin {
  readonly name = 'dev-server';

  private ctx!: PluginContext;
  private server!: Server;
  private wss!: WebSocketServer;
  private watcher!: FSWatcher;
  private port: number = DEFAULT_PORT;
  private timer: NodeJS.Timeout | null = null;
  private queue: Promise<void> = Promise.resolve();

  async onStart(ctx: PluginContext): Promise<void> {
    this.ctx = ctx;
    await this.setup();
  }

  getServer(): DevServer {
    return {
      server: this.server,
      wss: this.wss,
      port: this.port,
      close: () => this.close(),
    };
  }

  private async setup(): Promise<void> {
    const options = this.ctx.options as ServeOptions;
    const contentDir = options.contentDir;
    const outputDir = options.outputDir;
    const templatesDir = options.templatesDir ?? 'templates';
    const port = options.port ?? DEFAULT_PORT;

    await this.ctx.engine.rebuild();

    const wss = new WebSocketServer({ noServer: true });
    this.wss = wss;

    const server = createServer((req, res) => {
      serveFile(req.url ?? '/', outputDir, res).catch(() => {
        res.writeHead(500, { 'Content-Type': 'text/plain; charset=utf-8' });
        res.end('Internal Server Error');
      });
    });
    this.server = server;

    server.on('upgrade', (req, socket, head) => {
      const pathname = (req.url ?? '').split('?')[0];
      if (pathname === LIVERELOAD_PATH) {
        wss.handleUpgrade(req, socket, head, (ws) => {
          wss.emit('connection', ws, req);
        });
      } else {
        socket.destroy();
      }
    });

    const watcher = chokidar.watch([contentDir, templatesDir], {
      ignoreInitial: true,
      ignored: (watchedPath: string) => {
        const normalized = path.resolve(watchedPath);
        const out = path.resolve(outputDir);
        if (normalized === out || normalized.startsWith(out + path.sep)) {
          return true;
        }
        const segments = normalized.split(path.sep);
        if (segments.includes('node_modules')) {
          return true;
        }
        if (path.basename(normalized).startsWith('.')) {
          return true;
        }
        return false;
      },
    });
    this.watcher = watcher;
    watcher.on('error', () => {
      // Watcher errors are non-fatal for the dev server.
    });

    const watcherReady = new Promise<void>((resolve) => {
      watcher.once('ready', resolve);
    });

    watcher.on('all', () => {
      if (this.timer) {
        clearTimeout(this.timer);
      }
      this.timer = setTimeout(() => {
        this.timer = null;
        this.queue = this.queue.then(() => this.rebuild());
      }, REBUILD_DEBOUNCE_MS);
    });

    await watcherReady;
    await new Promise<void>((resolve) => setTimeout(resolve, WATCHER_SETTLE_MS));

    await new Promise<void>((resolve, reject) => {
      server.once('error', reject);
      server.listen(port, () => {
        server.removeListener('error', reject);
        resolve();
      });
    });

    const address = server.address();
    this.port = address && typeof address === 'object' ? address.port : port;
  }

  private broadcast(message: string): void {
    for (const client of this.wss.clients) {
      if (client.readyState === WebSocket.OPEN) {
        client.send(message);
      }
    }
  }

  private async rebuild(): Promise<void> {
    try {
      await this.ctx.engine.rebuild();
      this.broadcast('reload');
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      this.broadcast(JSON.stringify({ type: 'error', message }));
    }
  }

  private async close(): Promise<void> {
    if (this.timer) {
      clearTimeout(this.timer);
    }
    for (const client of this.wss.clients) {
      client.terminate();
    }
    await this.watcher.close();
    await new Promise<void>((resolve) => this.wss.close(() => resolve()));
    this.server.closeAllConnections();
    await new Promise<void>((resolve) => this.server.close(() => resolve()));
  }
}
