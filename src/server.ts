import http from 'http';
import fs from 'fs';
import path from 'path';
import { WebSocketServer, WebSocket } from 'ws';
import { watch, FSWatcher } from 'chokidar';
import { build } from './generate';

export interface DevServerOptions {
  contentDir: string;
  outputDir: string;
  templatesDir?: string;
  port: number;
  host?: string;
  debounceMs?: number;
}

export const RELOAD_MESSAGE = 'reload';

export const LIVE_RELOAD_SCRIPT =
  '<script data-ssg-live-reload>(function(){try{var ws=new WebSocket("ws://"+location.host);' +
  'ws.onmessage=function(e){if(e.data==="reload"){location.reload();}};}catch(err){}})();</script>';

const MIME_TYPES: Record<string, string> = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.webp': 'image/webp',
  '.ico': 'image/x-icon',
  '.txt': 'text/plain; charset=utf-8',
  '.md': 'text/markdown; charset=utf-8',
  '.xml': 'application/xml; charset=utf-8',
};

export function injectReloadScript(html: string): string {
  const idx = html.lastIndexOf('</body>');
  if (idx === -1) return html + LIVE_RELOAD_SCRIPT;
  return html.slice(0, idx) + LIVE_RELOAD_SCRIPT + html.slice(idx);
}

export class DevServer {
  private readonly options: DevServerOptions;
  private server: http.Server | null = null;
  private wss: WebSocketServer | null = null;
  private watcher: FSWatcher | null = null;
  private rebuildTimer: NodeJS.Timeout | null = null;

  constructor(options: DevServerOptions) {
    this.options = options;
  }

  build(): number {
    const pages = build({
      contentDir: this.options.contentDir,
      outputDir: this.options.outputDir,
      templatesDir: this.options.templatesDir,
    });
    return pages.length;
  }

  start(): Promise<void> {
    return new Promise<void>((resolve, reject) => {
      try {
        this.build();
      } catch (err) {
        reject(err);
        return;
      }

      this.server = http.createServer((req, res) => this.handleRequest(req, res));
      this.wss = new WebSocketServer({ server: this.server });

      this.server.once('error', reject);
      this.server.listen(this.options.port, this.options.host ?? 'localhost', async () => {
        this.server?.removeListener('error', reject);
        try {
          await this.startWatcher();
          resolve();
        } catch (err) {
          reject(err);
        }
      });
    });
  }

  stop(): Promise<void> {
    return new Promise<void>((resolve) => {
      if (this.rebuildTimer) {
        clearTimeout(this.rebuildTimer);
        this.rebuildTimer = null;
      }

      const finish = () => resolve();

      const closeWatcher = async () => {
        if (this.watcher) {
          const watcher = this.watcher;
          this.watcher = null;
          await watcher.close();
        }
        closeServer();
      };

      const closeServer = () => {
        if (this.wss) {
          for (const client of this.wss.clients) {
            client.terminate();
          }
          this.wss.close();
          this.wss = null;
        }
        if (this.server) {
          const server = this.server;
          this.server = null;
          server.close(() => finish());
        } else {
          finish();
        }
      };

      void closeWatcher();
    });
  }

  address(): string | null {
    const addr = this.server?.address();
    if (addr && typeof addr === 'object') {
      return `http://${addr.address}:${addr.port}`;
    }
    return null;
  }

  port(): number {
    const addr = this.server?.address();
    if (addr && typeof addr === 'object') {
      return addr.port;
    }
    return this.options.port;
  }

  private handleRequest(req: http.IncomingMessage, res: http.ServerResponse): void {
    const rawPath = (req.url || '/').split('?')[0];
    let urlPath: string;
    try {
      urlPath = decodeURIComponent(rawPath);
    } catch {
      urlPath = rawPath;
    }

    if (urlPath === '/') urlPath = '/index.html';

    const root = path.resolve(this.options.outputDir);
    let filePath = path.resolve(root, '.' + urlPath);

    if (filePath !== root && !filePath.startsWith(root + path.sep)) {
      res.writeHead(403, { 'Content-Type': 'text/plain; charset=utf-8' });
      res.end('Forbidden');
      return;
    }

    if (fs.existsSync(filePath) && fs.statSync(filePath).isDirectory()) {
      filePath = path.join(filePath, 'index.html');
    }

    if (!fs.existsSync(filePath) || !fs.statSync(filePath).isFile()) {
      res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
      res.end('Not found');
      return;
    }

    const ext = path.extname(filePath).toLowerCase();
    const contentType = MIME_TYPES[ext] ?? 'application/octet-stream';

    let body: string | Buffer = fs.readFileSync(filePath);
    if (ext === '.html') {
      body = injectReloadScript(body.toString('utf-8'));
    }

    res.writeHead(200, {
      'Content-Type': contentType,
      'Cache-Control': 'no-store',
    });
    res.end(body);
  }

  private startWatcher(): Promise<void> {
    const templatesDir = this.options.templatesDir ?? path.join(process.cwd(), 'templates');
    const paths = [this.options.contentDir, templatesDir];

    return new Promise<void>((resolve) => {
      this.watcher = watch(paths, { ignoreInitial: true });
      this.watcher.on('all', () => this.scheduleRebuild());
      this.watcher.on('ready', () => resolve());
    });
  }

  private scheduleRebuild(): void {
    if (this.rebuildTimer) clearTimeout(this.rebuildTimer);
    this.rebuildTimer = setTimeout(() => {
      this.rebuildTimer = null;
      this.rebuild();
    }, this.options.debounceMs ?? 100);
  }

  private rebuild(): void {
    try {
      this.build();
      this.broadcast(RELOAD_MESSAGE);
    } catch (err) {
      console.error('Rebuild failed:', err instanceof Error ? err.message : String(err));
    }
  }

  private broadcast(message: string): void {
    if (!this.wss) return;
    for (const client of this.wss.clients) {
      if (client.readyState === WebSocket.OPEN) {
        client.send(message);
      }
    }
  }
}
