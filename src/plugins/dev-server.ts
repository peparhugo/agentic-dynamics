import { existsSync, readFileSync, statSync } from 'node:fs';
import { createServer, IncomingMessage, Server, ServerResponse } from 'node:http';
import { extname, join, resolve, sep } from 'node:path';
import chokidar, { FSWatcher } from 'chokidar';
import { WebSocketServer } from 'ws';
import { buildSite, BuildOptions } from '../site';
import type { Plugin } from './plugin';

export interface DevelopmentServer {
  server: Server;
  close(): Promise<void>;
}

const reloadScript = '<script>(() => { const socket = new WebSocket(`ws://${location.host}/__ssg_reload`); socket.onmessage = () => location.reload(); })();</script>';
const contentTypes: Record<string, string> = { '.css': 'text/css; charset=utf-8', '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.json': 'application/json; charset=utf-8', '.svg': 'image/svg+xml' };

function serveFile(outputDir: string, request: IncomingMessage, response: ServerResponse): void {
  const requestedFile = new URL(request.url ?? '/', 'http://localhost').pathname === '/' ? 'index.html' : new URL(request.url ?? '/', 'http://localhost').pathname.replace(/^\/+/, '');
  const file = resolve(outputDir, requestedFile);
  if (file !== outputDir && !file.startsWith(`${outputDir}${sep}`)) return void response.writeHead(403).end('Forbidden');
  const path = existsSync(file) && statSync(file).isDirectory() ? join(file, 'index.html') : file;
  if (!existsSync(path) || !statSync(path).isFile()) return void response.writeHead(404).end('Not found');
  const type = contentTypes[extname(path).toLowerCase()] ?? 'application/octet-stream';
  response.writeHead(200, { 'Content-Type': type });
  response.end(extname(path).toLowerCase() === '.html' ? readFileSync(path, 'utf8').replace(/<\/body\s*>/i, `${reloadScript}</body>`) : readFileSync(path));
}

export class DevServerPlugin implements Plugin {
  start(options: BuildOptions & { port?: number } = {}): DevelopmentServer {
    const outputDir = resolve(options.outputDir ?? 'dist');
    const contentDir = resolve(options.contentDir ?? 'content');
    const templatesDir = resolve(options.templatesDir ?? 'templates');
    let webSocketServer: WebSocketServer;
    const build = (): void => {
      try {
        buildSite({ ...options, contentDir, outputDir, templatesDir });
        webSocketServer.clients.forEach((client) => client.send('reload'));
        process.stdout.write('Rebuilt site.\n');
      } catch (error) { process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`); }
    };
    buildSite({ ...options, contentDir, outputDir, templatesDir });
    const server = createServer((request, response) => serveFile(outputDir, request, response));
    webSocketServer = new WebSocketServer({ noServer: true });
    server.on('upgrade', (request, socket, head) => {
      if (new URL(request.url ?? '/', 'http://localhost').pathname !== '/__ssg_reload') return socket.destroy();
      webSocketServer.handleUpgrade(request, socket, head, (client) => webSocketServer.emit('connection', client, request));
    });
    const watcher: FSWatcher = chokidar.watch([contentDir, templatesDir], { ignoreInitial: true });
    watcher.on('all', build);
    server.listen(options.port ?? 3000, 'localhost');
    return { server, close: async () => { await watcher.close(); webSocketServer.close(); await new Promise<void>((done, reject) => server.close((error) => error ? reject(error) : done())); } };
  }
}
