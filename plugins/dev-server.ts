import fs from 'fs';
import http from 'http';
import path from 'path';
import { AddressInfo } from 'net';
import { WebSocket, WebSocketServer } from 'ws';
import chokidar, { FSWatcher } from 'chokidar';
import { Plugin, PluginContext } from '../src/plugin';
import type { SSGEngine } from '../src/engine';
import type { ServeOptions, DevServer } from '../src/serve';
import { DEFAULT_SERVE_PORT, LIVE_RELOAD_PATH, injectLiveReload, MIME_TYPES } from '../src/serve-helpers';

/**
 * Built-in plugin implementing the development server: static file serving of
 * the output directory with WebSocket-based live reload and a file watcher
 * that triggers rebuilds when content or templates change.
 */
export class DevServerPlugin implements Plugin {
  readonly name = 'dev-server';

  private readonly options: ServeOptions;
  private engine: SSGEngine | undefined;
  private server: http.Server | undefined;
  private wss: WebSocketServer | undefined;
  private watcher: FSWatcher | undefined;
  private rebuildTimer: ReturnType<typeof setTimeout> | null = null;
  private boundPort = 0;
  private started = false;
  private rebuilding = false;
  private pending = false;

  constructor(options: ServeOptions) {
    this.options = options;
  }

  attach(engine: SSGEngine): void {
    this.engine = engine;
  }

  onStart(_ctx: PluginContext): void {
    if (this.started) {
      return;
    }
    this.started = true;

    const outputDir = path.resolve(this.options.outputDir ?? 'dist');
    const contentDir = path.resolve(this.options.contentDir ?? 'content');
    const templateDir = path.resolve(this.options.templateDir ?? 'templates');
    const port = this.options.port ?? DEFAULT_SERVE_PORT;
    const host = this.options.host ?? '127.0.0.1';

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
    server.once('listening', () => {
      const address = server.address() as AddressInfo | null;
      if (address && typeof address === 'object') {
        this.boundPort = address.port;
      }
    });

    const watchPaths = [contentDir, templateDir].filter((dir) => fs.existsSync(dir));
    const watcher = chokidar.watch(watchPaths, { ignoreInitial: false });

    watcher.on('all', (_event, filePath) => {
      if (filePath.startsWith(outputDir + path.sep)) {
        return;
      }
      if (this.rebuildTimer) {
        clearTimeout(this.rebuildTimer);
      }
      this.rebuildTimer = setTimeout(() => {
        this.rebuildTimer = null;
        this.rebuild();
      }, 50);
    });

    this.server = server;
    this.wss = wss;
    this.watcher = watcher;
  }

  private broadcastReload(): void {
    if (!this.wss) {
      return;
    }
    for (const client of this.wss.clients) {
      if (client.readyState === WebSocket.OPEN) {
        client.send('reload');
      }
    }
  }

  rebuild(): void {
    if (!this.engine) {
      return;
    }
    if (this.rebuilding) {
      this.pending = true;
      return;
    }
    this.rebuilding = true;
    try {
      this.engine.buildOnce(this.options);
    } catch (err) {
      console.error('[ssg] rebuild failed:', err instanceof Error ? err.message : err);
    } finally {
      this.rebuilding = false;
      if (this.pending) {
        this.pending = false;
        this.rebuild();
      }
    }
  }

  afterBuild(ctx: PluginContext): void {
    console.log(`[ssg] rebuilt ${ctx.pages.length} page(s)`);
    this.broadcastReload();
  }

  onEnd(): void {
    if (!this.started) {
      return;
    }
    this.started = false;
    if (this.rebuildTimer) {
      clearTimeout(this.rebuildTimer);
      this.rebuildTimer = null;
    }
    if (this.wss) {
      for (const client of this.wss.clients) {
        client.terminate();
      }
      this.wss.close();
      this.wss = undefined;
    }
    if (this.watcher) {
      this.watcher.close();
      this.watcher = undefined;
    }
    if (this.server) {
      this.server.close();
      this.server.closeIdleConnections();
      this.server = undefined;
    }
  }

  get dev(): DevServer {
    const plugin = this;
    return {
      server: plugin.server as http.Server,
      wss: plugin.wss as WebSocketServer,
      get port() {
        return plugin.boundPort;
      },
      watcher: plugin.watcher as FSWatcher,
      rebuild: () => plugin.rebuild(),
      close: async () => {
        await plugin.engine?.stop();
      },
    };
  }
}
