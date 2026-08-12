import { promises as fs } from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { WebSocketServer, WebSocket } from 'ws';
import chokidar from 'chokidar';
import { buildSite, type BuildOptions } from './generator';

export interface ServeOptions extends BuildOptions {
  port?: number;
  host?: string;
}

export interface DevServer {
  server: http.Server;
  watcher: ReturnType<typeof chokidar.watch>;
  close: () => Promise<void>;
}

const liveReloadScript = (port: number): string => `<script>
(function () {
  var socket = new WebSocket('ws://' + location.hostname + ':${port}');
  socket.onmessage = function (event) { if (event.data === 'reload') location.reload(); };
  socket.onclose = function () { setTimeout(function () { location.reload(); }, 1000); };
}());
</script>`;

const injectLiveReload = (html: string, port: number): string => {
  const script = liveReloadScript(port);
  const closingBody = html.lastIndexOf('</body>');
  return closingBody >= 0
    ? `${html.slice(0, closingBody)}${script}${html.slice(closingBody)}`
    : `${html}${script}`;
};

const contentType = (filePath: string): string => {
  if (filePath.endsWith('.html')) return 'text/html; charset=utf-8';
  if (filePath.endsWith('.css')) return 'text/css; charset=utf-8';
  if (filePath.endsWith('.js')) return 'text/javascript; charset=utf-8';
  return 'application/octet-stream';
};

export async function startDevServer(options: ServeOptions = {}): Promise<DevServer> {
  const port = options.port ?? 3000;
  const host = options.host ?? 'localhost';
  const outputDir = path.resolve(options.outputDir ?? './dist');
  const contentDir = path.resolve(options.contentDir ?? './content');
  const templatesDir = path.resolve(options.templatesDir ?? './templates');
  let serverPort = port;
  let rebuilding = false;
  let queued = false;

  await buildSite({ contentDir, outputDir, templatesDir });

  const server = http.createServer(async (request, response) => {
    try {
      const requestPath = decodeURIComponent((request.url ?? '/').split('?')[0]);
      const relativePath = requestPath === '/' ? 'index.html' : requestPath.replace(/^\/+/, '');
      const filePath = path.resolve(outputDir, relativePath);
      if (filePath !== outputDir && !filePath.startsWith(`${outputDir}${path.sep}`)) {
        response.writeHead(403).end('Forbidden');
        return;
      }
      const file = await fs.readFile(filePath);
      const body = filePath.endsWith('.html') ? injectLiveReload(file.toString('utf8'), serverPort) : file;
      response.writeHead(200, { 'Content-Type': contentType(filePath) }).end(body);
    } catch {
      response.writeHead(404).end('Not found');
    }
  });
  const webSocketServer = new WebSocketServer({ server });
  const clients = new Set<WebSocket>();
  webSocketServer.on('connection', (socket) => {
    clients.add(socket);
    socket.on('close', () => clients.delete(socket));
  });

  const rebuild = async (): Promise<void> => {
    if (rebuilding) {
      queued = true;
      return;
    }
    rebuilding = true;
    try {
      await buildSite({ contentDir, outputDir, templatesDir });
      for (const client of clients) if (client.readyState === WebSocket.OPEN) client.send('reload');
    } catch (error) {
      process.stderr.write(`Build failed: ${error instanceof Error ? error.message : String(error)}\n`);
    } finally {
      rebuilding = false;
      if (queued) {
        queued = false;
        void rebuild();
      }
    }
  };
  const watcher = chokidar.watch([contentDir, templatesDir], { ignoreInitial: true });
  watcher.on('all', () => void rebuild());

  await new Promise<void>((resolve, reject) => {
    server.once('error', reject);
    server.listen(port, host, () => {
      server.removeListener('error', reject);
      const address = server.address();
      if (address && typeof address === 'object') serverPort = address.port;
      resolve();
    });
  });

  return {
    server,
    watcher,
    close: async () => {
      await watcher.close();
      for (const client of clients) client.terminate();
      await new Promise<void>((resolve) => {
        if (!webSocketServer.clients.size) {
          resolve();
          return;
        }
        webSocketServer.close(() => resolve());
      });
      await new Promise<void>((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
    },
  };
}
