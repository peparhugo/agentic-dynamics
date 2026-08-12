import fs from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';
import chokidar, { type FSWatcher } from 'chokidar';
import { WebSocketServer } from 'ws';
import type { Plugin, BuildContext } from '../src/plugin';
import { buildSite } from '../src/ssg';

export interface DevServer { server: http.Server; watcher: FSWatcher; webSocketServer: WebSocketServer; outputDir: string; port: number; close(): Promise<void>; }
const reloadScript = `<script>(function () {\n  function connect() {\n    var socket = new WebSocket((location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/__ssg_ws');\n    socket.onmessage = function (event) { if (event.data === 'reload') location.reload(); };\n    socket.onclose = function () { setTimeout(connect, 500); };\n  }\n  connect();\n}());</script>`;
function inject(document: string): string { const position = document.search(/<\/body\s*>/i); return position < 0 ? `${document}${reloadScript}` : `${document.slice(0, position)}${reloadScript}${document.slice(position)}`; }
function type(filePath: string): string { switch (path.extname(filePath).toLowerCase()) { case '.html': return 'text/html; charset=utf-8'; case '.css': return 'text/css; charset=utf-8'; case '.js': return 'text/javascript; charset=utf-8'; case '.json': return 'application/json; charset=utf-8'; case '.svg': return 'image/svg+xml'; case '.png': return 'image/png'; case '.jpg': case '.jpeg': return 'image/jpeg'; default: return 'application/octet-stream'; } }

export class DevServerPlugin implements Plugin {
  private result?: DevServer;
  private rebuild: Promise<void> = Promise.resolve();
  constructor(private readonly port = 3000) {}
  get server(): DevServer | undefined { return this.result; }

  async onStart(context: BuildContext): Promise<void> {
    if (!Number.isInteger(this.port) || this.port < 0 || this.port > 65535) throw new Error(`Invalid port: ${this.port}`);
    const { outputDir, contentDir, templatesDir } = context.options;
    const webSocketServer = new WebSocketServer({ noServer: true });
    const server = http.createServer(async (request, response) => {
      try {
        const requestedPath = decodeURIComponent(new URL(request.url ?? '/', 'http://localhost').pathname);
        const relativePath = requestedPath === '/' ? 'index.html' : requestedPath.replace(/^\/+/, '');
        const filePath = path.resolve(outputDir, relativePath);
        if (filePath !== outputDir && !filePath.startsWith(`${outputDir}${path.sep}`)) { response.writeHead(404).end('Not found'); return; }
        const data = await fs.readFile(filePath);
        const body = path.extname(filePath).toLowerCase() === '.html' ? Buffer.from(inject(data.toString('utf8'))) : data;
        response.writeHead(200, { 'Content-Type': type(filePath), 'Content-Length': body.length }).end(body);
      } catch (error: unknown) { const status = (error as NodeJS.ErrnoException).code === 'ENOENT' ? 404 : 500; response.writeHead(status).end(status === 404 ? 'Not found' : 'Internal server error'); }
    });
    server.on('upgrade', (request, socket, head) => { if (new URL(request.url ?? '/', 'http://localhost').pathname !== '/__ssg_ws') { socket.destroy(); return; } webSocketServer.handleUpgrade(request, socket, head, (client) => webSocketServer.emit('connection', client, request)); });
    const watcher = chokidar.watch([contentDir, templatesDir], { ignoreInitial: true });
    watcher.on('all', () => {
      this.rebuild = this.rebuild.then(async () => {
        await buildSite(context.options);
        webSocketServer.clients.forEach((client) => { if (client.readyState === 1) client.send('reload'); });
      }).catch((error: unknown) => console.error(error instanceof Error ? error.message : error));
    });
    await new Promise<void>((resolve, reject) => { server.once('error', reject); server.listen(this.port, 'localhost', () => { server.removeListener('error', reject); resolve(); }); });
    const address = server.address();
    this.result = { server, watcher, webSocketServer, outputDir, port: typeof address === 'object' && address ? address.port : this.port, async close() { await watcher.close(); webSocketServer.clients.forEach((client) => client.close()); await new Promise<void>((resolve, reject) => server.close((error) => error ? reject(error) : resolve())); await new Promise<void>((resolve) => webSocketServer.close(() => resolve())); } };
  }
}

export default function devServerPlugin(): Plugin { return new DevServerPlugin(); }
