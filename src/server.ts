import { existsSync, readFileSync, statSync } from 'node:fs';
import { createServer, IncomingMessage, Server, ServerResponse } from 'node:http';
import { extname, join, normalize, resolve, sep } from 'node:path';
import chokidar, { FSWatcher } from 'chokidar';
import { WebSocketServer } from 'ws';
import { BuildOptions, buildSite } from './site';

export interface ServeOptions extends BuildOptions {
  port?: number;
}

export interface DevelopmentServer {
  server: Server;
  close(): Promise<void>;
}

const reloadScript = '<script>(() => { const socket = new WebSocket(`ws://${location.host}/__ssg_reload`); socket.onmessage = () => location.reload(); })();</script>';

const contentTypes: Record<string, string> = {
  '.css': 'text/css; charset=utf-8',
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml'
};

function serveFile(outputDir: string, request: IncomingMessage, response: ServerResponse): void {
  const requestPath = new URL(request.url ?? '/', 'http://localhost').pathname;
  const requestedFile = requestPath === '/' ? 'index.html' : requestPath.replace(/^\/+/, '');
  const file = resolve(outputDir, requestedFile);
  if (file !== outputDir && !file.startsWith(`${outputDir}${sep}`)) {
    response.writeHead(403).end('Forbidden');
    return;
  }

  const path = existsSync(file) && statSync(file).isDirectory() ? join(file, 'index.html') : file;
  if (!existsSync(path) || !statSync(path).isFile()) {
    response.writeHead(404).end('Not found');
    return;
  }

  const type = contentTypes[extname(path).toLowerCase()] ?? 'application/octet-stream';
  if (extname(path).toLowerCase() === '.html') {
    response.writeHead(200, { 'Content-Type': type });
    response.end(readFileSync(path, 'utf8').replace(/<\/body\s*>/i, `${reloadScript}</body>`));
    return;
  }
  response.writeHead(200, { 'Content-Type': type });
  response.end(readFileSync(path));
}

export function startDevelopmentServer(options: ServeOptions = {}): DevelopmentServer {
  const outputDir = resolve(options.outputDir ?? 'dist');
  const contentDir = resolve(options.contentDir ?? 'content');
  const templatesDir = resolve(options.templatesDir ?? 'templates');
  const build = (): void => {
    try {
      buildSite({ contentDir, outputDir, templatesDir });
      webSocketServer.clients.forEach((client) => client.send('reload'));
      process.stdout.write('Rebuilt site.\n');
    } catch (error) {
      process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
    }
  };

  buildSite({ contentDir, outputDir, templatesDir });
  const server = createServer((request, response) => serveFile(outputDir, request, response));
  const webSocketServer = new WebSocketServer({ noServer: true });
  server.on('upgrade', (request, socket, head) => {
    if (new URL(request.url ?? '/', 'http://localhost').pathname !== '/__ssg_reload') return socket.destroy();
    webSocketServer.handleUpgrade(request, socket, head, (client) => webSocketServer.emit('connection', client, request));
  });
  const watcher: FSWatcher = chokidar.watch([contentDir, templatesDir], { ignoreInitial: true });
  watcher.on('all', build);
  server.listen(options.port ?? 3000, 'localhost');

  return {
    server,
    close: async () => {
      await watcher.close();
      webSocketServer.close();
      await new Promise<void>((resolveClose, reject) => server.close((error) => error ? reject(error) : resolveClose()));
    }
  };
}
