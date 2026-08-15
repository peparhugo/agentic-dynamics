import http from 'http';
import fs from 'fs';
import path from 'path';
import type { AddressInfo } from 'net';
import chokidar, { FSWatcher } from 'chokidar';
import { WebSocket, WebSocketServer } from 'ws';
import { buildSite } from './generator';

export interface DevServerOptions {
  contentDir: string;
  outputDir: string;
  templateDir?: string;
  port?: number;
}

export const RELOAD_PATH = '/__ssg_live_reload';
const LIVE_RELOAD_SCRIPT_ID = 'ssg-live-reload';
const DEFAULT_REBUILD_DELAY_MS = 50;

const MIME_TYPES: Record<string, string> = {
  '.html': 'text/html; charset=utf-8',
  '.htm': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.webp': 'image/webp',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
  '.ttf': 'font/ttf',
  '.otf': 'font/otf',
  '.map': 'application/json; charset=utf-8',
  '.txt': 'text/plain; charset=utf-8',
  '.xml': 'application/xml; charset=utf-8',
};

/**
 * Build the client-side script that connects to the dev server's WebSocket
 * and reloads the page when a `reload` message arrives.
 */
export function liveReloadScript(wsUrl: string): string {
  const safeUrl = JSON.stringify(wsUrl);
  return [
    `<script id="${LIVE_RELOAD_SCRIPT_ID}">`,
    '(function () {',
    '  function connect() {',
    '    var ws = new WebSocket(' + safeUrl + ');',
    '    ws.addEventListener("message", function (event) {',
    '      var data = event.data;',
    '      if (typeof data === "string") {',
    '        try {',
    '          var parsed = JSON.parse(data);',
    '          if (parsed && parsed.type === "reload") {',
    '            window.location.reload();',
    '            return;',
    '          }',
    '        } catch (e) { /* not json */ }',
    '        if (data === "reload") {',
    '          window.location.reload();',
    '        }',
    '      }',
    '    });',
    '    ws.addEventListener("close", function () {',
    '      setTimeout(connect, 1000);',
    '    });',
    '  }',
    '  connect();',
    '})();',
    '</script>',
  ].join('\n');
}

/**
 * Inject the live reload script into an HTML document, right before the
 * closing `</body>` tag. Pages that already contain the script are returned
 * untouched.
 */
export function injectLiveReload(html: string, wsUrl: string): string {
  if (html.indexOf(LIVE_RELOAD_SCRIPT_ID) !== -1) {
    return html;
  }
  const script = liveReloadScript(wsUrl);
  const bodyEnd = html.lastIndexOf('</body>');
  if (bodyEnd === -1) {
    return `${html}\n${script}\n`;
  }
  return `${html.slice(0, bodyEnd)}\n${script}\n${html.slice(bodyEnd)}`;
}

export function buildWsUrl(hostHeader: string | undefined): string {
  const host = hostHeader || 'localhost';
  return `ws://${host}${RELOAD_PATH}`;
}

export interface DevServer {
  server: http.Server;
  wss: WebSocketServer;
  watcher: FSWatcher;
  port: number;
  reload(): void;
  rebuild(): void;
  close(): Promise<void>;
}

/**
 * Live-reload development server for the static site generator.
 *
 * Watches the content and template directories, rebuilds the site into the
 * output directory whenever a watched file changes, and notifies connected
 * browsers over WebSocket so they reload automatically. Static files are
 * served from the output directory with the live reload script injected into
 * HTML pages.
 */
export class LiveReloadDevServer implements DevServer {
  readonly server: http.Server;
  readonly wss: WebSocketServer;
  readonly watcher: FSWatcher;
  port: number;

  private readonly options: DevServerOptions;
  private readonly clients = new Set<WebSocket>();
  private rebuildTimer: NodeJS.Timeout | null = null;

  constructor(options: DevServerOptions) {
    this.options = options;
    this.port = options.port ?? 3000;

    this.server = http.createServer((req, res) => this.handleRequest(req, res));
    this.wss = new WebSocketServer({ server: this.server, path: RELOAD_PATH });
    this.wss.on('connection', (ws: WebSocket) => {
      this.clients.add(ws);
      ws.on('close', () => {
        this.clients.delete(ws);
      });
    });

    this.watcher = chokidar.watch(this.watchTargets(), {
      ignoreInitial: true,
    });
    this.watcher.on('all', () => this.scheduleRebuild());
  }

  private watchTargets(): string[] {
    const targets = [path.resolve(this.options.contentDir)];
    if (this.options.templateDir !== undefined) {
      targets.push(path.resolve(this.options.templateDir));
      return targets;
    }
    const defaultTemplates = path.resolve('templates');
    if (fs.existsSync(defaultTemplates) && fs.statSync(defaultTemplates).isDirectory()) {
      targets.push(defaultTemplates);
    }
    return targets;
  }

  private handleRequest(req: http.IncomingMessage, res: http.ServerResponse): void {
    let pathname: string;
    try {
      pathname = decodeURIComponent(new URL(req.url || '/', 'http://localhost').pathname);
    } catch {
      res.writeHead(400, { 'Content-Type': 'text/plain; charset=utf-8' });
      res.end('Bad Request');
      return;
    }
    if (pathname === '/') {
      pathname = '/index.html';
    }

    const outputDir = path.resolve(this.options.outputDir);
    let filePath = path.resolve(outputDir, `.${pathname}`);
    if (filePath !== outputDir && !filePath.startsWith(`${outputDir}${path.sep}`)) {
      res.writeHead(403, { 'Content-Type': 'text/plain; charset=utf-8' });
      res.end('Forbidden');
      return;
    }

    if (fs.existsSync(filePath) && fs.statSync(filePath).isDirectory()) {
      filePath = path.join(filePath, 'index.html');
    }

    if (!fs.existsSync(filePath) || !fs.statSync(filePath).isFile()) {
      res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
      res.end('Not Found');
      return;
    }

    const ext = path.extname(filePath).toLowerCase();
    const contentType = MIME_TYPES[ext] || 'application/octet-stream';
    const body = fs.readFileSync(filePath);

    if (contentType.startsWith('text/html')) {
      const html = injectLiveReload(body.toString('utf8'), buildWsUrl(req.headers.host));
      res.writeHead(200, {
        'Content-Type': contentType,
        'Content-Length': Buffer.byteLength(html),
      });
      res.end(html);
      return;
    }

    res.writeHead(200, { 'Content-Type': contentType, 'Content-Length': body.length });
    res.end(body);
  }

  private scheduleRebuild(): void {
    if (this.rebuildTimer !== null) {
      clearTimeout(this.rebuildTimer);
    }
    this.rebuildTimer = setTimeout(() => {
      this.rebuildTimer = null;
      this.rebuild();
    }, DEFAULT_REBUILD_DELAY_MS);
  }

  /**
   * Rebuild the site and notify connected browsers when it succeeds.
   * Returns true when the rebuild completed without errors.
   */
  rebuild(): boolean {
    try {
      buildSite({
        contentDir: this.options.contentDir,
        outputDir: this.options.outputDir,
        templateDir: this.options.templateDir,
      });
      this.reload();
      return true;
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      console.error(`Rebuild failed: ${message}`);
      return false;
    }
  }

  /**
   * Broadcast a `reload` message to every connected WebSocket client.
   */
  reload(): void {
    const message = JSON.stringify({ type: 'reload' });
    for (const client of this.clients) {
      if (client.readyState === WebSocket.OPEN) {
        client.send(message);
      }
    }
  }

  async close(): Promise<void> {
    if (this.rebuildTimer !== null) {
      clearTimeout(this.rebuildTimer);
      this.rebuildTimer = null;
    }
    await this.watcher.close();
    for (const client of this.clients) {
      client.terminate();
    }
    this.clients.clear();
    await new Promise<void>((resolve) => this.wss.close(() => resolve()));
    await new Promise<void>((resolve) => {
      this.server.close(() => resolve());
      if (typeof this.server.closeAllConnections === 'function') {
        this.server.closeAllConnections();
      }
    });
  }
}

/**
 * Start the dev server and wait until it is listening. Uses an ephemeral
 * port when `port` is 0. An initial build is performed so the output
 * directory is up to date before the server starts serving.
 */
export function startDevServer(options: DevServerOptions): Promise<LiveReloadDevServer> {
  return new Promise((resolve, reject) => {
    const devServer = new LiveReloadDevServer(options);

    let initialBuildError: unknown;
    try {
      buildSite({
        contentDir: options.contentDir,
        outputDir: options.outputDir,
        templateDir: options.templateDir,
      });
    } catch (error) {
      initialBuildError = error;
    }

    if (initialBuildError !== undefined) {
      devServer.watcher.close().catch(() => undefined);
      reject(initialBuildError);
      return;
    }

    const listening = new Promise<void>((resolveListen, rejectListen) => {
      devServer.server.once('error', rejectListen);
      devServer.server.once('listening', () => {
        devServer.server.removeListener('error', rejectListen);
        const address = devServer.server.address() as AddressInfo | null;
        if (address && typeof address === 'object') {
          devServer.port = address.port;
        }
        resolveListen();
      });
      devServer.server.listen(devServer.port);
    });
    const watcherReady = new Promise<void>((resolveReady) => {
      devServer.watcher.once('ready', () => resolveReady());
    });

    Promise.all([listening, watcherReady])
      .then(() => resolve(devServer))
      .catch((error) => {
        devServer.watcher.close().catch(() => undefined);
        reject(error);
      });
  });
}
