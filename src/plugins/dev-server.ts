import fs from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';
import { createReadStream } from 'node:fs';
import chokidar, { FSWatcher } from 'chokidar';
import { WebSocket, WebSocketServer } from 'ws';
import { Plugin, PluginContext } from '../plugin';

export interface DevServerOptions { port?: number }
export interface DevServer {
  server: http.Server;
  watcher: FSWatcher;
  webSocketServer: WebSocketServer;
  close: () => Promise<void>;
}

const liveReloadScript = `<script>(function(){var ws=new WebSocket((location.protocol==='https:'?'wss://':'ws://')+location.host);ws.onmessage=function(event){if(event.data==='reload')location.reload();};})();</script>`;
function injectLiveReload(html: string): string {
  const closingBody = html.search(/<\/body\s*>/i);
  return closingBody === -1 ? `${html}${liveReloadScript}` : `${html.slice(0, closingBody)}${liveReloadScript}${html.slice(closingBody)}`;
}

async function serveFile(outputDir: string, requestPath: string, response: http.ServerResponse): Promise<void> {
  const pathname = decodeURIComponent(requestPath.split('?')[0]);
  const relative = pathname === '/' ? 'index.html' : pathname.replace(/^\/+/, '');
  const file = path.resolve(outputDir, relative);
  if (file !== outputDir && !file.startsWith(`${outputDir}${path.sep}`)) { response.writeHead(403); response.end('Forbidden'); return; }
  try {
    const stats = await fs.stat(file);
    if (!stats.isFile()) throw new Error('Not a file');
    if (path.extname(file).toLowerCase() === '.html') {
      response.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
      response.end(injectLiveReload(await fs.readFile(file, 'utf8')));
    } else { response.writeHead(200); createReadStream(file).pipe(response); }
  } catch { response.writeHead(404); response.end('Not found'); }
}

export class DevServerPlugin implements Plugin {
  private instance?: DevServer;
  private rebuilding = false;
  private pending = false;
  constructor(private readonly options: DevServerOptions = {}) {}

  async onStart(context: PluginContext): Promise<void> {
    if (this.instance) return;
    const webSocketServer = new WebSocketServer({ noServer: true });
    const server = http.createServer((request, response) => { void serveFile(context.options.outputDir, request.url ?? '/', response); });
    server.on('upgrade', (request, socket, head) => webSocketServer.handleUpgrade(request, socket, head, (client) => webSocketServer.emit('connection', client, request)));
    webSocketServer.on('connection', (client) => client.send('connected'));
    const watcher = chokidar.watch([context.options.contentDir, context.options.templatesDir], { ignoreInitial: true });
    const rebuild = async (): Promise<void> => {
      if (this.rebuilding) { this.pending = true; return; }
      this.rebuilding = true;
      try {
        await context.rebuild();
        webSocketServer.clients.forEach((client) => { if (client.readyState === WebSocket.OPEN) client.send('reload'); });
      } catch (error) { console.error(error instanceof Error ? error.message : error); }
      finally { this.rebuilding = false; if (this.pending) { this.pending = false; void rebuild(); } }
    };
    watcher.on('all', () => { void rebuild(); });
    await new Promise<void>((resolve) => server.listen(this.options.port ?? 3000, 'localhost', resolve));
    this.instance = { server, watcher, webSocketServer, close: async () => {
      await watcher.close(); webSocketServer.clients.forEach((client) => client.close());
      await new Promise<void>((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
      await new Promise<void>((resolve) => webSocketServer.close(() => resolve()));
    } };
  }

  get server(): DevServer | undefined { return this.instance; }
}

export default DevServerPlugin;
