import * as http from 'http';
import * as fs from 'fs';
import * as path from 'path';
import chokidar from 'chokidar';
import { WebSocketServer } from 'ws';
import { buildSite, DEFAULT_CONTENT_DIR, DEFAULT_OUTPUT_DIR, DEFAULT_TEMPLATES_DIR } from './build';
import type { BuildOptions } from './build';

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

export async function startDevServer(options: DevServerOptions): Promise<DevServerInstance> {
  const contentDir = path.resolve(options.contentDir ?? DEFAULT_CONTENT_DIR);
  const outputDir = path.resolve(options.outputDir ?? DEFAULT_OUTPUT_DIR);
  const templatesDir = options.templatesDir
    ? path.resolve(options.templatesDir)
    : path.resolve(DEFAULT_TEMPLATES_DIR);
  const host = options.host ?? DEFAULT_HOST;
  const rebuildDelay = options.rebuildDelay ?? 100;

  const buildOptions: BuildOptions = {
    contentDir,
    outputDir,
    templatesDir,
    siteTitle: options.siteTitle,
    defaultTemplate: options.defaultTemplate,
    defaultLayout: options.defaultLayout,
  };

  const server = http.createServer(createRequestHandler(outputDir));
  const wss = new WebSocketServer({ server, path: WS_PATH });

  let debounceTimer: NodeJS.Timeout | null = null;
  let closed = false;

  async function rebuild(): Promise<number> {
    const pages = await buildSite(buildOptions);
    return pages.length;
  }

  function broadcast(message: string): void {
    if (closed) return;
    for (const client of wss.clients) {
      if (client.readyState === client.OPEN) {
        client.send(message);
      }
    }
  }

  function scheduleRebuild(): void {
    if (closed) return;
    if (debounceTimer) {
      clearTimeout(debounceTimer);
    }
    debounceTimer = setTimeout(() => {
      debounceTimer = null;
      if (closed) return;
      rebuild()
        .then((count) => {
          console.log(`Rebuilt ${count} page(s)`);
          broadcast('reload');
        })
        .catch((error) => {
          console.error(`Rebuild failed: ${(error as Error).message}`);
        });
    }, rebuildDelay);
  }

  await rebuild();

  const watcher = chokidar.watch([contentDir, templatesDir], {
    ignoreInitial: true,
    persistent: true,
  });
  watcher.on('all', (event, changePath) => {
    if (closed) return;
    console.log(`${event}: ${changePath}`);
    scheduleRebuild();
  });
  await new Promise<void>((resolve) => watcher.once('ready', () => resolve()));

  await new Promise<void>((resolve, reject) => {
    server.once('error', reject);
    server.listen(options.port, host, () => {
      server.removeListener('error', reject);
      resolve();
    });
  });

  const address = server.address();
  const actualPort = address && typeof address === 'object' ? address.port : options.port;

  async function close(): Promise<void> {
    closed = true;
    if (debounceTimer) {
      clearTimeout(debounceTimer);
      debounceTimer = null;
    }
    await watcher.close();
    for (const client of wss.clients) {
      client.terminate();
    }
    await new Promise<void>((resolve) => wss.close(() => resolve()));
    await new Promise<void>((resolve) => server.close(() => resolve()));
  }

  return { server, wss, port: actualPort, outputDir, rebuild, broadcast, close };
}
