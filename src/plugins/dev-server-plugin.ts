import fs from 'fs';
import http from 'http';
import path from 'path';
import { watch, FSWatcher } from 'chokidar';
import { WebSocketServer, WebSocket } from 'ws';
import { Plugin } from '../plugin';
import { BuildOptions, DevServer, ServeOptions, Site } from '../types';

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

/**
 * Built-in plugin that owns the live-reload development server: it performs an
 * initial build, serves the generated site over HTTP, injects the WebSocket
 * client script into HTML responses, watches the content and templates
 * directories for changes, rebuilds on change, and tells connected browsers to
 * reload when a rebuild completes.
 */
export class DevServerPlugin implements Plugin {
  name = 'dev-server';

  private server?: http.Server;
  private wss?: WebSocketServer;
  private watcher?: FSWatcher;
  private timer: NodeJS.Timeout | null = null;
  private building = false;
  private pending = false;

  private readonly contentDir: string;
  private readonly outputDir: string;
  private readonly templatesDir: string;
  private readonly host: string;
  private readonly port: number;
  private readonly debounce: number;

  constructor(
    private readonly build: (options: BuildOptions) => Site,
    options: ServeOptions = {}
  ) {
    this.contentDir = path.resolve(options.contentDir ?? 'content');
    this.outputDir = path.resolve(options.outputDir ?? 'dist');
    this.templatesDir = path.resolve(options.templatesDir ?? 'templates');
    this.host = options.host ?? '127.0.0.1';
    this.port = options.port ?? 3000;
    this.debounce = options.debounce ?? 100;
  }

  onStart(): void {
    // The initial build and server setup are performed by start().
  }

  async onEnd(): Promise<void> {
    await this.close();
  }

  async start(): Promise<DevServer> {
    await this.onStart();

    this.build({
      contentDir: this.contentDir,
      outputDir: this.outputDir,
      templatesDir: this.templatesDir,
    });

    const server = http.createServer(createRequestHandler(this.outputDir));
    const wss = new WebSocketServer({ server });

    const watcher = watch([this.contentDir, this.templatesDir], { ignoreInitial: true });
    const watcherReady = new Promise<void>((resolve) => {
      watcher.once('ready', () => resolve());
    });

    watcher.on('all', () => this.scheduleRebuild());

    await new Promise<void>((resolve, reject) => {
      server.once('error', reject);
      server.listen(this.port, this.host, () => resolve());
    });

    await watcherReady;

    this.server = server;
    this.wss = wss;
    this.watcher = watcher;

    const address = server.address();
    const actualPort = typeof address === 'object' && address !== null ? address.port : this.port;

    return {
      server,
      port: actualPort,
      contentDir: this.contentDir,
      outputDir: this.outputDir,
      templatesDir: this.templatesDir,
      watcher,
      close: () => this.close(),
    };
  }

  async close(): Promise<void> {
    const { server, wss, watcher } = this;
    return new Promise<void>((resolve) => {
      if (this.timer) {
        clearTimeout(this.timer);
        this.timer = null;
      }
      if (wss) {
        for (const client of wss.clients) {
          client.terminate();
        }
      }
      const finish = (): void => {
        if (wss) {
          wss.close(() => {
            if (server) {
              server.close(() => resolve());
            } else {
              resolve();
            }
          });
        } else if (server) {
          server.close(() => resolve());
        } else {
          resolve();
        }
      };
      if (watcher) {
        watcher.close().then(finish);
      } else {
        finish();
      }
    });
  }

  private rebuild(): void {
    if (this.building) {
      this.pending = true;
      return;
    }
    this.building = true;
    this.pending = false;
    try {
      this.build({
        contentDir: this.contentDir,
        outputDir: this.outputDir,
        templatesDir: this.templatesDir,
      });
      this.broadcast(RELOAD_MESSAGE);
    } catch (err) {
      console.error('Rebuild failed:', err);
    } finally {
      this.building = false;
      if (this.pending) {
        this.pending = false;
        this.scheduleRebuild();
      }
    }
  }

  private scheduleRebuild(): void {
    if (this.timer) {
      clearTimeout(this.timer);
    }
    this.timer = setTimeout(() => {
      this.timer = null;
      this.rebuild();
    }, this.debounce);
  }

  private broadcast(message: string): void {
    if (!this.wss) {
      return;
    }
    for (const client of this.wss.clients) {
      if (client.readyState === WebSocket.OPEN) {
        client.send(message);
      }
    }
  }
}
