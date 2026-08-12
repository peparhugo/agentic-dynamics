import { createServer, IncomingMessage, Server, ServerResponse } from 'http';
import { existsSync, readFileSync, statSync } from 'fs';
import { extname, join, resolve, sep } from 'path';
import { FSWatcher } from 'chokidar';
import { WebSocketServer } from 'ws';
import { SsgEngine, createEngine } from './ssg';
import { DevServerPlugin } from './plugins/dev-server';

export interface ServeOptions {
  content: string;
  output: string;
  templates: string;
  port: number;
}

export interface DevServer {
  server: Server;
  wss: WebSocketServer;
  watcher: FSWatcher;
  options: ServeOptions;
  address(): string;
  ready(): Promise<void>;
  close(): Promise<void>;
}

export const DEFAULT_PORT = 3000;

const HTML_EXTENSIONS = new Set(['.html', '.htm']);

function isHtmlFile(filePath: string): boolean {
  return HTML_EXTENSIONS.has(extname(filePath).toLowerCase());
}

function mimeTypeFor(filePath: string): string {
  const ext = extname(filePath).toLowerCase();
  const mime: Record<string, string> = {
    '.html': 'text/html; charset=utf-8',
    '.htm': 'text/html; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.js': 'application/javascript; charset=utf-8',
    '.mjs': 'application/javascript; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.map': 'application/json; charset=utf-8',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif': 'image/gif',
    '.svg': 'image/svg+xml',
    '.ico': 'image/x-icon',
    '.webp': 'image/webp',
    '.woff': 'font/woff',
    '.woff2': 'font/woff2',
    '.ttf': 'font/ttf',
  };
  return mime[ext] ?? 'application/octet-stream';
}

export function liveReloadScript(): string {
  return [
    '<script>',
    '(function () {',
    '  var proto = location.protocol === "https:" ? "wss://" : "ws://";',
    '  var ws = new WebSocket(proto + location.host);',
    '  ws.onmessage = function () { location.reload(); };',
    '  ws.onclose = function () { setTimeout(function () { location.reload(); }, 500); };',
    '})();',
    '</script>',
  ].join('\n');
}

export function injectLiveReload(html: string): string {
  const script = liveReloadScript();
  const index = html.lastIndexOf('</body>');
  if (index === -1) return html + script;
  return html.slice(0, index) + script + html.slice(index);
}

function handleRequest(req: IncomingMessage, res: ServerResponse, outputDir: string): void {
  let urlPath: string;
  try {
    urlPath = decodeURIComponent((req.url ?? '/').split('?')[0]);
  } catch {
    res.writeHead(400, { 'Content-Type': 'text/plain' });
    res.end('Bad Request');
    return;
  }
  if (urlPath.endsWith('/')) urlPath += 'index.html';

  const filePath = resolve(outputDir, '.' + urlPath);
  if (!filePath.startsWith(outputDir + sep)) {
    res.writeHead(403, { 'Content-Type': 'text/plain' });
    res.end('Forbidden');
    return;
  }

  let target = filePath;
  if (existsSync(target) && statSync(target).isDirectory()) {
    target = join(target, 'index.html');
  }
  if (!existsSync(target)) {
    res.writeHead(404, { 'Content-Type': 'text/plain' });
    res.end('Not Found');
    return;
  }

  const contents = readFileSync(target);
  const headers: Record<string, string> = { 'Content-Type': mimeTypeFor(target) };
  res.writeHead(200, headers);
  if (isHtmlFile(target)) {
    res.end(injectLiveReload(contents.toString('utf8')));
    return;
  }
  res.end(contents);
}

export function startDevServer(options: ServeOptions): DevServer {
  const contentDir = resolve(options.content);
  const templatesDir = resolve(options.templates);
  const outputDir = resolve(options.output);

  const devServerPlugin = new DevServerPlugin();
  const engine: SsgEngine = createEngine({
    contentDir,
    outputDir,
    templatesDir,
    plugins: [devServerPlugin],
  });
  devServerPlugin.setRebuild(() => {
    engine.build();
  });

  engine.start();
  engine.build();

  const wss = devServerPlugin.wss;
  const watcher = devServerPlugin.watcher as FSWatcher;

  const server = createServer((req, res) => {
    handleRequest(req, res, outputDir);
  });

  server.on('upgrade', (req, socket, head) => {
    wss.handleUpgrade(req, socket, head, (ws) => {
      wss.emit('connection', ws, req);
    });
  });

  server.listen(options.port);

  return {
    server,
    wss,
    watcher,
    options,
    address(): string {
      const addr = server.address();
      if (addr === null || typeof addr === 'string') return `http://localhost:${options.port}`;
      return `http://localhost:${addr.port}`;
    },
    ready(): Promise<void> {
      return devServerPlugin.ready();
    },
    close(): Promise<void> {
      return new Promise((resolveClose, rejectClose) => {
        wss.close();
        watcher
          .close()
          .then(() => {
            server.close((err) => {
              if (err) rejectClose(err);
              else resolveClose();
            });
          })
          .catch(rejectClose);
      });
    },
  };
}
