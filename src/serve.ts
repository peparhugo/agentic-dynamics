import fs from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';
import chokidar, { type FSWatcher } from 'chokidar';
import { WebSocketServer } from 'ws';
import { buildSite, type BuildOptions } from './ssg';

export interface DevServerOptions extends BuildOptions {
  port?: number;
}

export interface DevServer {
  server: http.Server;
  watcher: FSWatcher;
  webSocketServer: WebSocketServer;
  outputDir: string;
  port: number;
  close(): Promise<void>;
}

const reloadScript = `<script>(function () {
  function connect() {
    var socket = new WebSocket((location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/__ssg_ws');
    socket.onmessage = function (event) { if (event.data === 'reload') location.reload(); };
    socket.onclose = function () { setTimeout(connect, 500); };
  }
  connect();
}());</script>`;

function injectReloadScript(document: string): string {
  const closingBody = document.search(/<\/body\s*>/i);
  return closingBody === -1
    ? `${document}${reloadScript}`
    : `${document.slice(0, closingBody)}${reloadScript}${document.slice(closingBody)}`;
}

function contentType(filePath: string): string {
  switch (path.extname(filePath).toLowerCase()) {
    case '.html': return 'text/html; charset=utf-8';
    case '.css': return 'text/css; charset=utf-8';
    case '.js': return 'text/javascript; charset=utf-8';
    case '.json': return 'application/json; charset=utf-8';
    case '.svg': return 'image/svg+xml';
    case '.png': return 'image/png';
    case '.jpg': case '.jpeg': return 'image/jpeg';
    default: return 'application/octet-stream';
  }
}

export async function startDevServer(options: DevServerOptions = {}): Promise<DevServer> {
  const outputDir = path.resolve(options.outputDir ?? './dist');
  const contentDir = path.resolve(options.contentDir ?? './content');
  const templatesDir = path.resolve(options.templatesDir ?? './templates');
  const port = options.port ?? 3000;
  if (!Number.isInteger(port) || port < 0 || port > 65535) throw new Error(`Invalid port: ${port}`);

  await buildSite({ contentDir, outputDir, templatesDir });
  const webSocketServer = new WebSocketServer({ noServer: true });
  const server = http.createServer(async (request, response) => {
    try {
      const requestedPath = decodeURIComponent(new URL(request.url ?? '/', 'http://localhost').pathname);
      const relativePath = requestedPath === '/' ? 'index.html' : requestedPath.replace(/^\/+/, '');
      const filePath = path.resolve(outputDir, relativePath);
      if (filePath !== outputDir && !filePath.startsWith(`${outputDir}${path.sep}`)) {
        response.writeHead(404).end('Not found');
        return;
      }
      const data = await fs.readFile(filePath);
      const body = path.extname(filePath).toLowerCase() === '.html'
        ? Buffer.from(injectReloadScript(data.toString('utf8')))
        : data;
      response.writeHead(200, { 'Content-Type': contentType(filePath), 'Content-Length': body.length }).end(body);
    } catch (error: unknown) {
      const status = (error as NodeJS.ErrnoException).code === 'ENOENT' ? 404 : 500;
      response.writeHead(status).end(status === 404 ? 'Not found' : 'Internal server error');
    }
  });
  server.on('upgrade', (request, socket, head) => {
    if (new URL(request.url ?? '/', 'http://localhost').pathname !== '/__ssg_ws') {
      socket.destroy();
      return;
    }
    webSocketServer.handleUpgrade(request, socket, head, (client) => webSocketServer.emit('connection', client, request));
  });

  let rebuild: Promise<void> = Promise.resolve();
  const watcher = chokidar.watch([contentDir, templatesDir], { ignoreInitial: true });
  const rebuildSite = () => {
    rebuild = rebuild.then(async () => {
      await buildSite({ contentDir, outputDir, templatesDir });
      webSocketServer.clients.forEach((client) => {
        if (client.readyState === 1) client.send('reload');
      });
    }).catch((error: unknown) => console.error(error instanceof Error ? error.message : error));
  };
  watcher.on('all', rebuildSite);

  await new Promise<void>((resolve, reject) => {
    server.once('error', reject);
    server.listen(port, 'localhost', () => {
      server.removeListener('error', reject);
      resolve();
    });
  });
  const address = server.address();
  const actualPort = typeof address === 'object' && address ? address.port : port;

  return {
    server, watcher, webSocketServer, outputDir, port: actualPort,
    async close() {
      await watcher.close();
      webSocketServer.clients.forEach((client) => client.close());
      await new Promise<void>((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
      await new Promise<void>((resolve) => webSocketServer.close(() => resolve()));
    },
  };
}
