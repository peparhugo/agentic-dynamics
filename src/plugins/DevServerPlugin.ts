import fs from 'fs';
import http from 'http';
import path from 'path';
import chokidar from 'chokidar';
import type { FSWatcher } from 'chokidar';
import { WebSocketServer, WebSocket } from 'ws';
import type { Plugin, PluginContext } from '../plugin';

export const DEFAULT_PORT = 3000;
export const RELOAD_PATH = '/__ssg_reload';
export const RELOAD_MESSAGE = 'reload';

const REBUILD_DEBOUNCE_MS = 100;

const MIME_TYPES: Record<string, string> = {
  '.html': 'text/html; charset=utf-8',
  '.htm': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.map': 'application/json; charset=utf-8',
  '.txt': 'text/plain; charset=utf-8',
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
  '.webmanifest': 'application/manifest+json',
};

export function injectReloadScript(html: string, wsPath: string = RELOAD_PATH): string {
  const script = [
    '<script>',
    '(function () {',
    `  var wsPath = ${JSON.stringify(wsPath)};`,
    "  var scheme = location.protocol === 'https:' ? 'wss://' : 'ws://';",
    '  var socket = new WebSocket(scheme + location.host + wsPath);',
    '  socket.onmessage = function (event) {',
    `    if (event.data === ${JSON.stringify(RELOAD_MESSAGE)}) {`,
    '      location.reload();',
    '    }',
    '  };',
    '})();',
    '</script>',
  ].join('\n');

  const bodyIndex = html.toLowerCase().lastIndexOf('</body>');
  if (bodyIndex === -1) {
    return `${html}\n${script}\n`;
  }
  return `${html.slice(0, bodyIndex)}\n${script}\n${html.slice(bodyIndex)}`;
}

export class DevServerPlugin implements Plugin {
  readonly name = 'dev-server';

  port: number = DEFAULT_PORT;
  outputDir = '';
  server: http.Server | null = null;
  ws: WebSocketServer | null = null;
  watcher: FSWatcher | null = null;

  private debounceTimer: NodeJS.Timeout | null = null;
  private ctx: PluginContext | null = null;

  onStart(ctx: PluginContext): void {
    this.ctx = ctx;
    const port = ctx.port ?? DEFAULT_PORT;
    const contentDir = ctx.contentDir;
    const templatesDir = ctx.templatesDir ?? 'templates';
    this.port = port;
    this.outputDir = ctx.outputDir;

    const resolveFile = (rootDir: string, urlPath: string): string | null => {
      let pathname: string;
      try {
        pathname = decodeURIComponent(urlPath);
      } catch {
        return null;
      }
      if (pathname === '/') {
        pathname = '/index.html';
      }
      const root = path.resolve(rootDir);
      let file = path.resolve(root, pathname.replace(/^\/+/, ''));
      if (file !== root && !file.startsWith(root + path.sep)) {
        return null;
      }
      if (fs.existsSync(file) && fs.statSync(file).isDirectory()) {
        file = path.join(file, 'index.html');
      }
      return file;
    };

    const sendStatus = (res: http.ServerResponse, status: number, text: string): void => {
      res.writeHead(status, { 'Content-Type': 'text/plain; charset=utf-8' });
      res.end(text);
    };

    const server = http.createServer((req, res) => {
      const method = (req.method || 'GET').toUpperCase();
      if (method !== 'GET' && method !== 'HEAD') {
        res.writeHead(405, { Allow: 'GET, HEAD' });
        res.end('Method Not Allowed');
        return;
      }

      let pathname = '/';
      try {
        pathname = new URL(req.url || '/', `http://localhost:${port}`).pathname;
      } catch {
        sendStatus(res, 400, 'Bad Request');
        return;
      }

      const file = resolveFile(this.outputDir, pathname);
      if (!file || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
        sendStatus(res, 404, 'Not Found');
        return;
      }

      const ext = path.extname(file).toLowerCase();
      const contentType = MIME_TYPES[ext] || 'application/octet-stream';
      const data = fs.readFileSync(file);

      if (contentType.startsWith('text/html')) {
        const body = injectReloadScript(data.toString('utf-8'));
        const headers: Record<string, string> = { 'Content-Type': contentType };
        if (method === 'HEAD') {
          headers['Content-Length'] = String(Buffer.byteLength(body));
        }
        res.writeHead(200, headers);
        if (method === 'HEAD') {
          res.end();
        } else {
          res.end(body);
        }
        return;
      }

      res.writeHead(200, { 'Content-Type': contentType });
      if (method === 'HEAD') {
        res.end();
      } else {
        res.end(data);
      }
    });
    this.server = server;

    const wss = new WebSocketServer({ noServer: true });
    this.ws = wss;

    server.on('upgrade', (req, socket, head) => {
      let pathname = '/';
      try {
        pathname = new URL(req.url || '/', `http://localhost:${port}`).pathname;
      } catch {
        pathname = '/';
      }
      if (pathname !== RELOAD_PATH && pathname !== '/') {
        socket.destroy();
        return;
      }
      wss.handleUpgrade(req, socket, head, (ws) => {
        wss.emit('connection', ws, req);
      });
    });

    const watcher = chokidar.watch([contentDir, templatesDir], {
      ignoreInitial: true,
    });
    this.watcher = watcher;

    watcher.on('all', () => {
      if (this.debounceTimer) {
        clearTimeout(this.debounceTimer);
      }
      this.debounceTimer = setTimeout(() => {
        this.debounceTimer = null;
        this.rebuild();
      }, REBUILD_DEBOUNCE_MS);
    });

    watcher.on('error', (err: unknown) => {
      this.reportError(err);
    });

    server.listen(port, () => {
      process.stdout.write(`ssg serve: listening on http://localhost:${port}\n`);
    });
  }

  afterBuild(ctx: PluginContext): void {
    if (ctx.onBuild && ctx.lastResult) {
      ctx.onBuild(ctx.lastResult);
    }
    this.broadcastReload();
  }

  onEnd(): void {
    if (this.debounceTimer) {
      clearTimeout(this.debounceTimer);
      this.debounceTimer = null;
    }
    if (this.watcher) {
      void this.watcher.close();
      this.watcher = null;
    }
    if (this.ws) {
      for (const client of this.ws.clients) {
        client.terminate();
      }
      this.ws.close();
      this.ws = null;
    }
    if (this.server) {
      if (typeof this.server.closeAllConnections === 'function') {
        this.server.closeAllConnections();
      }
      this.server.close();
      this.server = null;
    }
  }

  private rebuild(): void {
    const ctx = this.ctx;
    if (!ctx || !ctx.rebuild) {
      return;
    }
    try {
      ctx.rebuild();
    } catch (err) {
      this.reportError(err);
    }
  }

  private reportError(err: unknown): void {
    const ctx = this.ctx;
    const error = err instanceof Error ? err : new Error(String(err));
    if (ctx && ctx.onError) {
      ctx.onError(error);
    } else {
      process.stderr.write(`ssg serve: ${error.message}\n`);
    }
  }

  private broadcastReload(): void {
    if (!this.ws) {
      return;
    }
    const message = Buffer.from(RELOAD_MESSAGE);
    for (const client of this.ws.clients) {
      if (client.readyState === WebSocket.OPEN) {
        client.send(message);
      }
    }
  }
}
