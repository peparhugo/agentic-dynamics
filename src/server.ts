import { createReadStream, existsSync, readFileSync, statSync } from 'node:fs';
import { createServer, IncomingMessage, ServerResponse } from 'node:http';
import { extname, join, normalize, resolve } from 'node:path';
import chokidar, { FSWatcher } from 'chokidar';
import { WebSocketServer } from 'ws';
import { BuildOptions, buildSite } from './generator';

const liveReloadScript = `<script>(() => { const socket = new WebSocket((location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/__ssg_live_reload'); socket.addEventListener('message', () => location.reload()); })();</script>`;

const mimeTypes: Record<string, string> = {
  '.css': 'text/css; charset=utf-8',
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
};

export interface ServeOptions extends BuildOptions {
  port?: number;
}

export interface DevelopmentServer {
  close(): Promise<void>;
  port: number;
}

export function injectLiveReload(html: string): string {
  return /<\/body\s*>/i.test(html)
    ? html.replace(/<\/body\s*>/i, `${liveReloadScript}</body>`)
    : `${html}${liveReloadScript}`;
}

function serveFile(request: IncomingMessage, response: ServerResponse, outputDir: string): void {
  const urlPath = decodeURIComponent(new URL(request.url ?? '/', 'http://localhost').pathname);
  const relativePath = urlPath === '/' ? 'index.html' : urlPath.replace(/^\/+/, '');
  const root = resolve(outputDir);
  let filePath = resolve(root, normalize(relativePath));
  if (!filePath.startsWith(`${root}/`) && filePath !== root) {
    response.writeHead(403).end('Forbidden');
    return;
  }
  if (existsSync(filePath) && statSync(filePath).isDirectory()) filePath = join(filePath, 'index.html');
  if (!existsSync(filePath) || !statSync(filePath).isFile()) {
    response.writeHead(404).end('Not found');
    return;
  }

  const type = mimeTypes[extname(filePath).toLowerCase()] ?? 'application/octet-stream';
  if (extname(filePath).toLowerCase() === '.html') {
    response.writeHead(200, { 'content-type': type });
    response.end(injectLiveReload(readFileSync(filePath, 'utf8')));
    return;
  }
  response.writeHead(200, { 'content-type': type });
  createReadStream(filePath).pipe(response);
}

export function startServer({ contentDir = './content', outputDir = './dist', templatesDir = './templates', port = 3000 }: ServeOptions = {}): DevelopmentServer {
  const buildOptions = { contentDir, outputDir, templatesDir };
  buildSite(buildOptions);

  const server = createServer((request, response) => serveFile(request, response, outputDir));
  const webSockets = new WebSocketServer({ noServer: true });
  server.on('upgrade', (request, socket, head) => {
    if (new URL(request.url ?? '/', 'http://localhost').pathname !== '/__ssg_live_reload') {
      socket.destroy();
      return;
    }
    webSockets.handleUpgrade(request, socket, head, (client) => webSockets.emit('connection', client, request));
  });

  let rebuildTimer: NodeJS.Timeout | undefined;
  const watcher: FSWatcher = chokidar.watch([contentDir, templatesDir], { ignoreInitial: true });
  watcher.on('all', () => {
    clearTimeout(rebuildTimer);
    rebuildTimer = setTimeout(() => {
      try {
        const pages = buildSite(buildOptions);
        console.log(`Built ${pages.length} page${pages.length === 1 ? '' : 's'}. Reloading browsers.`);
        for (const client of webSockets.clients) client.send('reload');
      } catch (error) {
        console.error(error instanceof Error ? error.message : error);
      }
    }, 50);
  });

  server.listen(port, 'localhost', () => console.log(`Serving ${outputDir} at http://localhost:${port}`));
  return {
    port,
    close: async () => {
      clearTimeout(rebuildTimer);
      await watcher.close();
      for (const client of webSockets.clients) client.close();
      await new Promise<void>((resolveClose, rejectClose) => server.close((error) => error ? rejectClose(error) : resolveClose()));
    },
  };
}
