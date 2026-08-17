import * as fs from 'fs';
import * as http from 'http';
import * as path from 'path';
import { watch, FSWatcher } from 'chokidar';
import { WebSocketServer, WebSocket } from 'ws';
import { build } from './build';

export interface DevServerOptions {
  contentDir: string;
  outputDir: string;
  templatesDir?: string;
  port?: number;
}

const MIME_TYPES: Record<string, string> = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.mjs': 'application/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
  '.txt': 'text/plain; charset=utf-8',
};

const LIVE_RELOAD_SCRIPT =
  '<script>(function(){var ws=new WebSocket("ws://"+location.host);ws.onmessage=function(e){if(e.data==="reload"){location.reload();}};})();</script>';

/** Inject the live-reload WebSocket client into an HTML document. */
export function injectLiveReloadScript(html: string): string {
  const bodyTag = html.match(/<\/body\s*>/i);
  if (bodyTag) {
    return html.replace(bodyTag[0], `${LIVE_RELOAD_SCRIPT}${bodyTag[0]}`);
  }
  return html + LIVE_RELOAD_SCRIPT;
}

/**
 * A development server that serves the built site from the output directory,
 * watches the content and templates directories for changes, rebuilds on
 * change, and notifies connected browsers to reload.
 */
export class DevServer {
  private server: http.Server;
  private wss: WebSocketServer;
  private watcher: FSWatcher;
  private ready: Promise<void>;
  private options: { contentDir: string; outputDir: string; templatesDir: string };
  private port: number;
  private rebuildTimer: NodeJS.Timeout | null = null;

  constructor(options: DevServerOptions) {
    this.options = {
      contentDir: options.contentDir,
      outputDir: options.outputDir,
      templatesDir: options.templatesDir ?? './templates',
    };
    this.port = options.port ?? 3000;

    this.server = http.createServer((req, res) => this.handleRequest(req, res));
    this.wss = new WebSocketServer({ server: this.server });

    this.watcher = watch([this.options.contentDir, this.options.templatesDir], {
      ignoreInitial: true,
    });
    this.ready = new Promise((resolve) => this.watcher.once('ready', () => resolve()));
    this.watcher.on('all', () => this.scheduleRebuild());
  }

  private scheduleRebuild(): void {
    if (this.rebuildTimer) {
      clearTimeout(this.rebuildTimer);
    }
    this.rebuildTimer = setTimeout(() => {
      this.rebuildTimer = null;
      this.rebuild();
    }, 50);
  }

  private rebuild(): void {
    try {
      build({
        contentDir: this.options.contentDir,
        outputDir: this.options.outputDir,
        templatesDir: this.options.templatesDir,
      });
    } catch (err) {
      console.error('Build failed:', err);
      return;
    }
    for (const client of this.wss.clients) {
      if (client.readyState === WebSocket.OPEN) {
        client.send('reload');
      }
    }
  }

  private handleRequest(req: http.IncomingMessage, res: http.ServerResponse): void {
    const rawPath = (req.url || '/').split('?')[0];
    let pathname: string;
    try {
      pathname = decodeURIComponent(rawPath);
    } catch {
      res.writeHead(400, { 'Content-Type': 'text/plain; charset=utf-8' });
      res.end('Bad Request');
      return;
    }

    if (pathname === '/') {
      pathname = '/index.html';
    }

    const outputRoot = path.resolve(this.options.outputDir);
    const resolved = path.resolve(outputRoot, pathname.replace(/^\/+/, ''));

    if (resolved !== outputRoot && !resolved.startsWith(outputRoot + path.sep)) {
      res.writeHead(403, { 'Content-Type': 'text/plain; charset=utf-8' });
      res.end('Forbidden');
      return;
    }

    fs.readFile(resolved, (err, data) => {
      if (err) {
        res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
        res.end('Not Found');
        return;
      }

      const ext = path.extname(resolved).toLowerCase();
      const contentType = MIME_TYPES[ext] || 'application/octet-stream';
      const body = ext === '.html' ? Buffer.from(injectLiveReloadScript(data.toString('utf8'))) : data;

      res.writeHead(200, { 'Content-Type': contentType });
      res.end(body);
    });
  }

  /** Perform an initial build, start listening, and resolve to the bound port. */
  start(): Promise<number> {
    this.rebuild();
    return new Promise((resolve, reject) => {
      this.server.once('error', reject);
      this.server.listen(this.port, async () => {
        await this.ready;
        const address = this.server.address();
        const port = typeof address === 'object' && address !== null ? address.port : this.port;
        resolve(port);
      });
    });
  }

  /** Stop the watcher, disconnect clients, and close the servers. */
  async close(): Promise<void> {
    if (this.rebuildTimer) {
      clearTimeout(this.rebuildTimer);
      this.rebuildTimer = null;
    }
    await this.watcher.close();
    for (const client of this.wss.clients) {
      client.terminate();
    }
    await new Promise<void>((resolve) => this.wss.close(() => resolve()));
    await new Promise<void>((resolve) => this.server.close(() => resolve()));
  }
}
