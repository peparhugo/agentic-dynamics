import fs from 'fs';
import http from 'http';
import path from 'path';
import type { AddressInfo } from 'net';
import { watch, FSWatcher } from 'chokidar';
import { WebSocket, WebSocketServer } from 'ws';
import { buildSite } from './site';
import { DEFAULT_TEMPLATES_DIR } from './template';

export const DEFAULT_PORT = 3000;
export const LIVERELOAD_PATH = '/__livereload';
export const RELOAD_MESSAGE = 'reload';

export const REBUILD_DELAY_MS = 100;

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
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.txt': 'text/plain; charset=utf-8',
  '.xml': 'application/xml; charset=utf-8',
  '.webmanifest': 'application/manifest+json; charset=utf-8',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
  '.ttf': 'font/ttf',
  '.map': 'application/json; charset=utf-8',
};

export interface ServeOptions {
  contentDir: string;
  outputDir: string;
  templatesDir?: string;
  port?: number;
}

export interface ServeHandle {
  server: http.Server;
  wss: WebSocketServer;
  watcher: FSWatcher;
  port: number;
  close: () => Promise<void>;
}

export function clientScript(): string {
  return [
    '<script id="__livereload">',
    '(function () {',
    "  var proto = location.protocol === 'https:' ? 'wss://' : 'ws://';",
    `  var ws = new WebSocket(proto + location.host + '${LIVERELOAD_PATH}');`,
    `  ws.onmessage = function (event) {`,
    `    if (event.data === '${RELOAD_MESSAGE}') { location.reload(); }`,
    '  };',
    '})();',
    '</script>',
  ].join('\n');
}

export function hasLiveReload(html: string): boolean {
  return html.includes('id="__livereload"');
}

export function injectLiveReload(html: string): string {
  if (hasLiveReload(html)) return html;
  const script = clientScript();
  const bodyEnd = html.lastIndexOf('</body>');
  if (bodyEnd !== -1) {
    return html.slice(0, bodyEnd) + script + html.slice(bodyEnd);
  }
  const htmlEnd = html.lastIndexOf('</html>');
  if (htmlEnd !== -1) {
    return html.slice(0, htmlEnd) + script + html.slice(htmlEnd);
  }
  return html + script;
}

function contentType(filePath: string): string {
  return MIME_TYPES[path.extname(filePath).toLowerCase()] || 'application/octet-stream';
}

function isHtmlFile(filePath: string): boolean {
  return /\.html?$/i.test(filePath);
}

export function createRequestHandler(
  outputDir: string
): (req: http.IncomingMessage, res: http.ServerResponse) => void {
  return (req, res) => {
    let pathname: string;
    try {
      pathname = decodeURIComponent(new URL(req.url || '/', 'http://localhost').pathname);
    } catch {
      res.writeHead(400, { 'Content-Type': 'text/plain; charset=utf-8' });
      res.end('Bad request');
      return;
    }

    if (pathname === '/') pathname = '/index.html';

    const resolvedRoot = path.resolve(outputDir);
    const filePath = path.join(resolvedRoot, pathname);
    if (!filePath.startsWith(resolvedRoot + path.sep)) {
      res.writeHead(403, { 'Content-Type': 'text/plain; charset=utf-8' });
      res.end('Forbidden');
      return;
    }

    fs.readFile(filePath, (err, data) => {
      if (err) {
        res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
        res.end('Not found');
        return;
      }
      let body: string | Buffer = data;
      if (isHtmlFile(filePath) && !hasLiveReload(data.toString('utf8'))) {
        body = injectLiveReload(data.toString('utf8'));
      }
      res.writeHead(200, { 'Content-Type': contentType(filePath) });
      res.end(body);
    });
  };
}

export function broadcastReload(wss: WebSocketServer): void {
  for (const client of wss.clients) {
    if (client.readyState === WebSocket.OPEN) {
      client.send(RELOAD_MESSAGE);
    }
  }
}

export function serve(options: ServeOptions): ServeHandle {
  const contentDir = options.contentDir;
  const outputDir = options.outputDir;
  const templatesDir = options.templatesDir || DEFAULT_TEMPLATES_DIR;
  const port = options.port ?? DEFAULT_PORT;

  if (!fs.existsSync(contentDir)) {
    throw new Error(`content directory not found: ${contentDir}`);
  }

  buildSite(contentDir, outputDir, templatesDir);

  const server = http.createServer(createRequestHandler(outputDir));
  const wss = new WebSocketServer({ server, path: LIVERELOAD_PATH });

  const watchPaths: string[] = [contentDir];
  if (fs.existsSync(templatesDir)) watchPaths.push(templatesDir);

  const watcher = watch(watchPaths, { ignoreInitial: true });

  let timer: NodeJS.Timeout | null = null;
  watcher.on('all', () => {
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => {
      timer = null;
      try {
        buildSite(contentDir, outputDir, templatesDir);
        broadcastReload(wss);
      } catch (err) {
        console.error(
          '[ssg serve] rebuild failed:',
          err instanceof Error ? err.message : err
        );
      }
    }, REBUILD_DELAY_MS);
  });

  const handle: ServeHandle = {
    server,
    wss,
    watcher,
    port,
    close: (): Promise<void> =>
      new Promise((resolve) => {
        if (timer) {
          clearTimeout(timer);
          timer = null;
        }
        watcher.close().then(() => {
          wss.close(() => {
            server.close(() => resolve());
          });
        });
      }),
  };

  server.on('listening', () => {
    const addr = server.address() as AddressInfo;
    if (addr) {
      handle.port = addr.port;
      console.log(`[ssg serve] http://localhost:${addr.port}`);
    }
  });

  server.listen(port);
  return handle;
}
