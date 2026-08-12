import * as http from 'http';
import * as fs from 'fs';
import * as path from 'path';
import chokidar from 'chokidar';
import { WebSocketServer } from 'ws';
import { loadPlugins } from '../config';
import type { Plugin, SsgContext } from '../plugin';
import { Ssg, DEFAULT_CONTENT_DIR, DEFAULT_OUTPUT_DIR, DEFAULT_TEMPLATES_DIR } from '../ssg';
import type { BuildOptions } from '../ssg';
import type { Page } from '../types';

export interface DevServerOptions extends BuildOptions {
  port: number;
  host?: string;
  rebuildDelay?: number;
}

export interface DevServerInstance {
  server: http.Server;
  wss: WebSocketServer;
  port: number;
  outputDir: string;
  rebuild: () => Promise<number>;
  broadcast: (message: string) => void;
  close: () => Promise<void>;
}

export const DEFAULT_PORT = 3000;
export const DEFAULT_HOST = 'localhost';
export const WS_PATH = '/live-reload';

const LIVE_RELOAD_SCRIPT = [
  '<script>',
  '(function () {',
  '  var protocol = location.protocol === "https:" ? "wss:" : "ws:";',
  `  var socket = new WebSocket(protocol + "//" + location.host + "${WS_PATH}");`,
  '  socket.onmessage = function (event) {',
  '    if (event.data === "reload") {',
  '      location.reload();',
  '    }',
  '  };',
  '  socket.onclose = function () {',
  '    setTimeout(function () { location.reload(); }, 1000);',
  '  };',
  '})();',
  '</script>',
].join('\n');

export function injectLiveReloadScript(html: string): string {
  if (html.toLowerCase().includes('</body>')) {
    return html.replace(/<\/body>/i, `${LIVE_RELOAD_SCRIPT}\n</body>`);
  }
  if (html.toLowerCase().includes('</html>')) {
    return html.replace(/<\/html>/i, `${LIVE_RELOAD_SCRIPT}\n</html>`);
  }
  return `${html}\n${LIVE_RELOAD_SCRIPT}`;
}

function mimeType(filePath: string): string {
  const ext = path.extname(filePath).toLowerCase();
  switch (ext) {
    case '.html':
      return 'text/html; charset=utf-8';
    case '.css':
      return 'text/css; charset=utf-8';
    case '.js':
    case '.mjs':
      return 'application/javascript; charset=utf-8';
    case '.json':
      return 'application/json; charset=utf-8';
    case '.png':
      return 'image/png';
    case '.jpg':
    case '.jpeg':
      return 'image/jpeg';
    case '.gif':
      return 'image/gif';
    case '.svg':
      return 'image/svg+xml';
    case '.ico':
      return 'image/x-icon';
    case '.woff':
      return 'font/woff';
    case '.woff2':
      return 'font/woff2';
    default:
      return 'application/octet-stream';
  }
}

function createRequestHandler(outputDir: string): http.RequestListener {
  const resolvedOutputDir = path.resolve(outputDir);

  return (req: http.IncomingMessage, res: http.ServerResponse): void => {
    let urlPath = '/';
    try {
      urlPath = decodeURIComponent((req.url ?? '/').split('?')[0]);
    } catch {
      urlPath = '/';
    }

    let filePath = path.join(resolvedOutputDir, urlPath);
    const isDirectoryRequest = filePath.endsWith(path.sep) || filePath === resolvedOutputDir;
    if (isDirectoryRequest) {
      filePath = path.join(resolvedOutputDir, 'index.html');
    }

    const resolved = path.resolve(filePath);
    if (resolved !== resolvedOutputDir && !resolved.startsWith(resolvedOutputDir + path.sep)) {
      res.writeHead(403, { 'Content-Type': 'text/plain; charset=utf-8' });
      res.end('Forbidden');
      return;
    }

    const serveIndex = (): void => {
      const index = path.join(resolvedOutputDir, 'index.html');
      if (fs.existsSync(index)) {
        const html = injectLiveReloadScript(fs.readFileSync(index, 'utf8'));
        res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
        res.end(html);
        return;
      }
      res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
      res.end('Not Found');
    };

    if (!fs.existsSync(resolved) || !fs.statSync(resolved).isFile()) {
      if (!isDirectoryRequest && path.extname(urlPath) === '') {
        serveIndex();
        return;
      }
      res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
      res.end('Not Found');
      return;
    }

    const contentType = mimeType(resolved);
    const isText = contentType.startsWith('text/') || contentType === 'image/svg+xml';
    if (isText) {
      let text = fs.readFileSync(resolved, 'utf8');
      if (resolved.endsWith('.html')) {
        text = injectLiveReloadScript(text);
      }
      res.writeHead(200, { 'Content-Type': contentType });
      res.end(text);
      return;
    }

    res.writeHead(200, { 'Content-Type': contentType });
    res.end(fs.readFileSync(resolved));
  };
}

export class DevServerPlugin implements Plugin {
  readonly name = 'dev-server';

  private readonly options: DevServerOptions;
  private readonly engine: Ssg;
  private readonly buildPlugins: Plugin[];

  private server: http.Server | null = null;
  private wss: WebSocketServer | null = null;
  private watcher: ReturnType<typeof chokidar.watch> | null = null;
  private debounceTimer: NodeJS.Timeout | null = null;
  private closed = false;
  private actualPort = 0;
  private outputDir = '';

  constructor(options: DevServerOptions, buildPlugins: Plugin[]) {
    this.options = options;
    this.buildPlugins = buildPlugins;
    this.engine = new Ssg(buildPlugins);
  }

  getPlugins(): Plugin[] {
    return this.buildPlugins;
  }

  async onStart(context: SsgContext): Promise<void> {
    this.outputDir = context.outputDir;
  }

  async onEnd(_context: SsgContext): Promise<void> {
    // Server lifecycle is managed via start()/close().
  }

  async start(): Promise<DevServerInstance> {
    const contentDir = path.resolve(this.options.contentDir ?? DEFAULT_CONTENT_DIR);
    const outputDir = path.resolve(this.options.outputDir ?? DEFAULT_OUTPUT_DIR);
    const templatesDir = this.options.templatesDir
      ? path.resolve(this.options.templatesDir)
      : path.resolve(DEFAULT_TEMPLATES_DIR);
    const host = this.options.host ?? DEFAULT_HOST;
    const rebuildDelay = this.options.rebuildDelay ?? 100;
    this.outputDir = outputDir;

    const buildOptions: BuildOptions = {
      contentDir,
      outputDir,
      templatesDir,
      siteTitle: this.options.siteTitle,
      defaultTemplate: this.options.defaultTemplate,
      defaultLayout: this.options.defaultLayout,
    };
    this.buildOptions = buildOptions;

    this.server = http.createServer(createRequestHandler(outputDir));
    this.wss = new WebSocketServer({ server: this.server, path: WS_PATH });

    await this.rebuild();

    this.watcher = chokidar.watch([contentDir, templatesDir], {
      ignoreInitial: true,
      persistent: true,
    });
    this.watcher.on('all', (event, changePath) => {
      if (this.closed) return;
      console.log(`${event}: ${changePath}`);
      this.scheduleRebuild(rebuildDelay);
    });
    await new Promise<void>((resolve) => this.watcher!.once('ready', () => resolve()));

    await new Promise<void>((resolve, reject) => {
      this.server!.once('error', reject);
      this.server!.listen(this.options.port, host, () => {
        this.server!.removeListener('error', reject);
        resolve();
      });
    });

    const address = this.server!.address();
    this.actualPort = address && typeof address === 'object' ? address.port : this.options.port;

    return this.instance();
  }

  private buildOptions: BuildOptions | null = null;

  async rebuild(): Promise<number> {
    if (!this.buildOptions) return 0;
    const pages: Page[] = await this.engine.rebuild(this.buildOptions);
    return pages.length;
  }

  broadcast(message: string): void {
    if (this.closed || !this.wss) return;
    for (const client of this.wss.clients) {
      if (client.readyState === client.OPEN) {
        client.send(message);
      }
    }
  }

  async close(): Promise<void> {
    this.closed = true;
    if (this.debounceTimer) {
      clearTimeout(this.debounceTimer);
      this.debounceTimer = null;
    }
    if (this.watcher) {
      await this.watcher.close();
    }
    if (this.wss) {
      for (const client of this.wss.clients) {
        client.terminate();
      }
      await new Promise<void>((resolve) => this.wss!.close(() => resolve()));
    }
    if (this.server) {
      await new Promise<void>((resolve) => this.server!.close(() => resolve()));
    }
  }

  private scheduleRebuild(rebuildDelay: number): void {
    if (this.closed) return;
    if (this.debounceTimer) {
      clearTimeout(this.debounceTimer);
    }
    this.debounceTimer = setTimeout(() => {
      this.debounceTimer = null;
      if (this.closed) return;
      this.rebuild()
        .then((count) => {
          console.log(`Rebuilt ${count} page(s)`);
          this.broadcast('reload');
        })
        .catch((error) => {
          console.error(`Rebuild failed: ${(error as Error).message}`);
        });
    }, rebuildDelay);
  }

  private instance(): DevServerInstance {
    return {
      server: this.server!,
      wss: this.wss!,
      port: this.actualPort,
      outputDir: this.outputDir,
      rebuild: () => this.rebuild(),
      broadcast: (message: string) => this.broadcast(message),
      close: () => this.close(),
    };
  }
}

export async function startDevServer(options: DevServerOptions): Promise<DevServerInstance> {
  const plugins = await loadPlugins(options.configPath);
  const plugin = new DevServerPlugin(options, plugins);
  return await plugin.start();
}
