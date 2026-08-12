import { promises as fs } from 'fs';
import * as http from 'http';
import * as path from 'path';
import * as url from 'url';
import chokidar, { type FSWatcher } from 'chokidar';
import { WebSocketServer } from 'ws';

import type { Plugin, PluginContext } from '../plugin';
import { SSGEngine } from '../engine';

export interface ServeOptions {
  command: 'serve';
  contentDir: string;
  outputDir: string;
  templateDir: string;
  port: number;
}

export interface DevServer {
  server: http.Server;
  wss: WebSocketServer;
  watcher: FSWatcher;
  port: number;
  outputDir: string;
  close(): Promise<void>;
}

export const RELOAD_PATH = '/__livereload';

export const RELOAD_SCRIPT = `<script id="ssg-live-reload">
(function () {
  var scheme = location.protocol === 'https:' ? 'wss:' : 'ws:';
  var socket = new WebSocket(scheme + '//' + location.host + '${RELOAD_PATH}');
  socket.onmessage = function (event) {
    if (event.data === 'reload') {
      location.reload();
    }
  };
  socket.onclose = function () {
    setTimeout(function () {
      location.reload();
    }, 500);
  };
})();
</script>`;

export function injectReloadScript(html: string): string {
  if (html.includes('ssg-live-reload')) {
    return html;
  }
  const index = html.lastIndexOf('</body>');
  if (index === -1) {
    return `${html}\n${RELOAD_SCRIPT}\n`;
  }
  return `${html.slice(0, index)}${RELOAD_SCRIPT}${html.slice(index)}`;
}

const CONTENT_TYPES: Record<string, string> = {
  '.html': 'text/html; charset=utf-8',
  '.htm': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.txt': 'text/plain; charset=utf-8',
  '.md': 'text/markdown; charset=utf-8',
  '.xml': 'application/xml; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.webp': 'image/webp',
  '.ico': 'image/x-icon',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
};

function contentTypeFor(filePath: string): string {
  return CONTENT_TYPES[path.extname(filePath).toLowerCase()] ?? 'application/octet-stream';
}

function createRequestHandler(outputDir: string) {
  const root = path.resolve(outputDir);
  return async (req: http.IncomingMessage, res: http.ServerResponse): Promise<void> => {
    let pathname = '/';
    try {
      pathname = decodeURIComponent(url.parse(req.url ?? '/').pathname ?? '/');
    } catch {
      // fall through with '/'
    }
    const relative = pathname === '/' ? 'index.html' : pathname.replace(/^\/+/, '');
    const filePath = path.normalize(path.join(root, relative));
    if (!filePath.startsWith(root + path.sep)) {
      res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
      res.end('Not Found');
      return;
    }
    try {
      const data = await fs.readFile(filePath);
      const isHtml = /\.html?$/i.test(relative);
      const body = isHtml ? injectReloadScript(data.toString('utf8')) : data;
      res.writeHead(200, { 'Content-Type': contentTypeFor(filePath) });
      res.end(body);
    } catch {
      res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
      res.end('Not Found');
    }
  };
}

export class DevServerPlugin implements Plugin {
  name = 'dev-server';

  private server: http.Server | null = null;
  private wss: WebSocketServer | null = null;
  private watcher: FSWatcher | null = null;
  private rebuilding = false;
  private queued = false;

  afterBuild(_ctx: PluginContext): void {
    this.broadcastReload();
  }

  private broadcastReload(): void {
    if (!this.wss) {
      return;
    }
    for (const client of this.wss.clients) {
      if (client.readyState === client.OPEN) {
        client.send('reload');
      }
    }
  }

  private async rebuild(options: ServeOptions, engine: SSGEngine): Promise<void> {
    if (this.rebuilding) {
      this.queued = true;
      return;
    }
    this.rebuilding = true;
    try {
      const rebuilt = await engine.build(options);
      console.log(`Rebuilt ${rebuilt.length} page(s)`);
    } catch (err) {
      console.error(`Rebuild failed: ${(err as Error).message}`);
    } finally {
      this.rebuilding = false;
      if (this.queued) {
        this.queued = false;
        void this.rebuild(options, engine);
      }
    }
  }

  async start(options: ServeOptions, engine: SSGEngine): Promise<DevServer> {
    this.server = null;
    this.wss = null;
    this.watcher = null;
    this.rebuilding = false;
    this.queued = false;

    const pages = await engine.build(options);
    console.log(`Built ${pages.length} page(s) into ${path.resolve(options.outputDir)}`);

    const server = http.createServer(createRequestHandler(options.outputDir));
    const wss = new WebSocketServer({ server, path: RELOAD_PATH });
    const watcher = chokidar.watch([options.contentDir, options.templateDir], {
      ignoreInitial: true,
    });
    this.server = server;
    this.wss = wss;
    this.watcher = watcher;

    watcher.on('all', () => {
      void this.rebuild(options, engine);
    });

    await new Promise<void>((resolve) => {
      const timer = setTimeout(resolve, 2000);
      watcher.once('ready', () => {
        clearTimeout(timer);
        resolve();
      });
    });

    await new Promise<void>((resolve, reject) => {
      const onError = (err: Error): void => {
        server.off('listening', onListening);
        reject(err);
      };
      const onListening = (): void => {
        server.off('error', onError);
        resolve();
      };
      server.once('error', onError);
      server.once('listening', onListening);
      server.listen(options.port);
    });

    const address = server.address();
    const port =
      typeof address === 'object' && address !== null ? address.port : options.port;

    return {
      server,
      wss,
      watcher,
      port,
      outputDir: options.outputDir,
      close: () => this.close(),
    };
  }

  async close(): Promise<void> {
    if (this.wss) {
      for (const client of this.wss.clients) {
        client.terminate();
      }
      await new Promise<void>((resolveClose) => {
        this.wss!.close(() => resolveClose());
      });
      this.wss = null;
    }
    if (this.watcher) {
      await this.watcher.close();
      this.watcher = null;
    }
    if (this.server) {
      this.server.closeAllConnections();
      await new Promise<void>((resolveClose) => {
        this.server!.close(() => resolveClose());
      });
      this.server = null;
    }
  }
}

export async function startDevServer(options: ServeOptions): Promise<DevServer> {
  const engine = await SSGEngine.fromOptions(options, new DevServerPlugin());
  const dev = engine.pipeline.plugins.find(
    (plugin): plugin is DevServerPlugin => plugin instanceof DevServerPlugin
  );
  if (!dev) {
    throw new Error('DevServerPlugin was not registered in the plugin pipeline');
  }
  return dev.start(options, engine);
}
