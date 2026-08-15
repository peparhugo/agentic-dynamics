import http from 'http';
import fs from 'fs';
import path from 'path';
import chokidar, { FSWatcher } from 'chokidar';
import { WebSocket, WebSocketServer } from 'ws';
import { buildSite } from './generator';
import { SsgEngine } from './engine';
import { defaultPlugins } from './plugins';
import { DevServerPlugin } from './plugins/dev-server-plugin';
import type { Plugin, PluginFactory } from './plugins/types';

export interface DevServerOptions {
  contentDir: string;
  outputDir: string;
  templateDir?: string;
  port?: number;
  /**
   * Optional rebuild routine used instead of the default full-site build.
   * Return `true` when the rebuild succeeded so clients are reloaded.
   */
  rebuild?: () => boolean | Promise<boolean>;
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
  private readonly rebuildFn: () => boolean | Promise<boolean>;
  private readonly clients = new Set<WebSocket>();
  private rebuildTimer: NodeJS.Timeout | null = null;

  constructor(options: DevServerOptions) {
    this.options = options;
    this.port = options.port ?? 3000;
    this.rebuildFn = options.rebuild ?? (() => this.defaultRebuild());

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
      const result = this.rebuildFn();
      if (result && typeof (result as Promise<boolean>).then === 'function') {
        void (result as Promise<boolean>).then(() => this.reload());
        return true;
      }
      if (result === false) {
        return false;
      }
      this.reload();
      return true;
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      console.error(`Rebuild failed: ${message}`);
      return false;
    }
  }

  /**
   * Default rebuild routine: run the full site build, mirroring the behaviour
   * of the `build` command. Used when no custom `rebuild` is configured.
   */
  private defaultRebuild(): boolean {
    buildSite({
      contentDir: this.options.contentDir,
      outputDir: this.options.outputDir,
      templateDir: this.options.templateDir,
    });
    return true;
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
 *
 * The server is driven by the SSG engine's plugin pipeline: the built-in
 * dev-server plugin starts the HTTP/WebSocket server and rebuilds the site
 * through the markdown/template plugins on every change.
 */
export function startDevServer(
  options: DevServerOptions,
  extraPlugins: Array<Plugin | PluginFactory> = []
): Promise<LiveReloadDevServer> {
  const engine = new SsgEngine(
    {
      contentDir: options.contentDir,
      outputDir: options.outputDir,
      templateDir: options.templateDir,
      command: 'serve',
    },
    [...defaultPlugins('serve'), ...extraPlugins]
  );
  const devPlugin = engine.plugins.find(
    (plugin): plugin is DevServerPlugin => plugin instanceof DevServerPlugin
  );
  if (!devPlugin) {
    return Promise.reject(new Error('DevServerPlugin is required to start the dev server'));
  }
  return devPlugin.start(engine, options);
}
