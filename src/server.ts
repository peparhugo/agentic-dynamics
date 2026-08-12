import fs from 'fs';
import http from 'http';
import path from 'path';
import chokidar, { FSWatcher } from 'chokidar';
import { WebSocketServer, WebSocket } from 'ws';
import { buildSite } from './build';
import type { SiteBuildResult } from './build';

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

export interface DevServerOptions {
  port?: number;
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
  onBuild?: (result: SiteBuildResult) => void;
  onError?: (err: Error) => void;
}

export interface DevServer {
  port: number;
  outputDir: string;
  server: http.Server;
  ws: WebSocketServer;
  watcher: FSWatcher;
  close: () => Promise<void>;
}

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

export function startDevServer(options: DevServerOptions = {}): DevServer {
  const port = options.port ?? DEFAULT_PORT;
  const contentDir = options.contentDir ?? 'content';
  const outputDir = options.outputDir ?? 'dist';
  const templatesDir = options.templatesDir ?? 'templates';

  function reportError(err: unknown): void {
    const error = err instanceof Error ? err : new Error(String(err));
    if (options.onError) {
      options.onError(error);
    } else {
      process.stderr.write(`ssg serve: ${error.message}\n`);
    }
  }

  function reportSuccess(result: SiteBuildResult): void {
    if (options.onBuild) {
      options.onBuild(result);
    }
  }

  function resolveFile(rootDir: string, urlPath: string): string | null {
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
  }

  function sendStatus(res: http.ServerResponse, status: number, text: string): void {
    res.writeHead(status, { 'Content-Type': 'text/plain; charset=utf-8' });
    res.end(text);
  }

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

    const file = resolveFile(outputDir, pathname);
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

  const wss = new WebSocketServer({ noServer: true });

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

  function broadcastReload(): void {
    const message = Buffer.from(RELOAD_MESSAGE);
    for (const client of wss.clients) {
      if (client.readyState === WebSocket.OPEN) {
        client.send(message);
      }
    }
  }

  function rebuild(): void {
    try {
      const result = buildSite(contentDir, outputDir, templatesDir);
      reportSuccess(result);
      broadcastReload();
    } catch (err) {
      reportError(err);
    }
  }

  let debounceTimer: NodeJS.Timeout | null = null;

  const watcher = chokidar.watch([contentDir, templatesDir], {
    ignoreInitial: true,
  });

  watcher.on('all', () => {
    if (debounceTimer) {
      clearTimeout(debounceTimer);
    }
    debounceTimer = setTimeout(() => {
      debounceTimer = null;
      rebuild();
    }, REBUILD_DEBOUNCE_MS);
  });

  watcher.on('error', (err: unknown) => {
    reportError(err);
  });

  try {
    const result = buildSite(contentDir, outputDir, templatesDir);
    reportSuccess(result);
  } catch (err) {
    reportError(err);
  }

  server.listen(port, () => {
    process.stdout.write(`ssg serve: listening on http://localhost:${port}\n`);
  });

  async function close(): Promise<void> {
    if (debounceTimer) {
      clearTimeout(debounceTimer);
      debounceTimer = null;
    }
    await watcher.close();
    for (const client of wss.clients) {
      client.terminate();
    }
    wss.close();
    if (typeof server.closeAllConnections === 'function') {
      server.closeAllConnections();
    }
    await new Promise<void>((resolve) => {
      server.close(() => resolve());
    });
  }

  return { port, outputDir, server, ws: wss, watcher, close };
}
