import { promises as fs } from 'fs';
import * as http from 'http';
import * as path from 'path';
import * as url from 'url';
import chokidar, { type FSWatcher } from 'chokidar';
import { WebSocketServer } from 'ws';

import { build } from './ssg';

export interface ServeOptions {
  command: 'serve';
  contentDir: string;
  outputDir: string;
  templateDir: string;
  port: number;
}

export interface DevServer {
  server: http.Server;
  wss: WebSocketServer;
  watcher: FSWatcher;
  port: number;
  outputDir: string;
  close(): Promise<void>;
}

export const RELOAD_PATH = '/__livereload';

export const RELOAD_SCRIPT = `<script id="ssg-live-reload">
(function () {
  var scheme = location.protocol === 'https:' ? 'wss:' : 'ws:';
  var socket = new WebSocket(scheme + '//' + location.host + '${RELOAD_PATH}');
  socket.onmessage = function (event) {
    if (event.data === 'reload') {
      location.reload();
    }
  };
  socket.onclose = function () {
    setTimeout(function () {
      location.reload();
    }, 500);
  };
})();
</script>`;

export function injectReloadScript(html: string): string {
  if (html.includes('ssg-live-reload')) {
    return html;
  }
  const index = html.lastIndexOf('</body>');
  if (index === -1) {
    return `${html}\n${RELOAD_SCRIPT}\n`;
  }
  return `${html.slice(0, index)}${RELOAD_SCRIPT}${html.slice(index)}`;
}

const CONTENT_TYPES: Record<string, string> = {
  '.html': 'text/html; charset=utf-8',
  '.htm': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.txt': 'text/plain; charset=utf-8',
  '.md': 'text/markdown; charset=utf-8',
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
};

function contentTypeFor(filePath: string): string {
  return CONTENT_TYPES[path.extname(filePath).toLowerCase()] ?? 'application/octet-stream';
}

function createRequestHandler(outputDir: string) {
  const root = path.resolve(outputDir);
  return async (req: http.IncomingMessage, res: http.ServerResponse): Promise<void> => {
    let pathname = '/';
    try {
      pathname = decodeURIComponent(url.parse(req.url ?? '/').pathname ?? '/');
    } catch {
      // fall through with '/'
    }
    const relative = pathname === '/' ? 'index.html' : pathname.replace(/^\/+/, '');
    const filePath = path.normalize(path.join(root, relative));
    if (!filePath.startsWith(root + path.sep)) {
      res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
      res.end('Not Found');
      return;
    }
    try {
      const data = await fs.readFile(filePath);
      const isHtml = /\.html?$/i.test(relative);
      const body = isHtml ? injectReloadScript(data.toString('utf8')) : data;
      res.writeHead(200, { 'Content-Type': contentTypeFor(filePath) });
      res.end(body);
    } catch {
      res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
      res.end('Not Found');
    }
  };
}

export async function startDevServer(options: ServeOptions): Promise<DevServer> {
  const pages = await build({
    contentDir: options.contentDir,
    outputDir: options.outputDir,
    templateDir: options.templateDir,
  });
  console.log(`Built ${pages.length} page(s) into ${path.resolve(options.outputDir)}`);

  const server = http.createServer(createRequestHandler(options.outputDir));
  const wss = new WebSocketServer({ server, path: RELOAD_PATH });
  const watcher = chokidar.watch([options.contentDir, options.templateDir], {
    ignoreInitial: true,
  });

  let rebuilding = false;
  let queued = false;

  function broadcastReload(): void {
    for (const client of wss.clients) {
      if (client.readyState === client.OPEN) {
        client.send('reload');
      }
    }
  }

  async function rebuild(): Promise<void> {
    if (rebuilding) {
      queued = true;
      return;
    }
    rebuilding = true;
    try {
      const rebuilt = await build({
        contentDir: options.contentDir,
        outputDir: options.outputDir,
        templateDir: options.templateDir,
      });
      console.log(`Rebuilt ${rebuilt.length} page(s)`);
      broadcastReload();
    } catch (err) {
      console.error(`Rebuild failed: ${(err as Error).message}`);
    } finally {
      rebuilding = false;
      if (queued) {
        queued = false;
        void rebuild();
      }
    }
  }

  watcher.on('all', () => {
    void rebuild();
  });

  await new Promise<void>((resolve) => {
    const timer = setTimeout(resolve, 2000);
    watcher.once('ready', () => {
      clearTimeout(timer);
      resolve();
    });
  });

  await new Promise<void>((resolve, reject) => {
    const onError = (err: Error): void => {
      server.off('listening', onListening);
      reject(err);
    };
    const onListening = (): void => {
      server.off('error', onError);
      resolve();
    };
    server.once('error', onError);
    server.once('listening', onListening);
    server.listen(options.port);
  });

  const address = server.address();
  const port =
    typeof address === 'object' && address !== null ? address.port : options.port;

  async function close(): Promise<void> {
    for (const client of wss.clients) {
      client.terminate();
    }
    await watcher.close();
    await new Promise<void>((resolveClose) => {
      wss.close(() => resolveClose());
    });
    server.closeAllConnections();
    await new Promise<void>((resolveClose) => {
      server.close(() => resolveClose());
    });
  }

  return { server, wss, watcher, port, outputDir: options.outputDir, close };
}
