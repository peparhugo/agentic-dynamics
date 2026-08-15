import fs from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';
import { createReadStream } from 'node:fs';
import chokidar, { FSWatcher } from 'chokidar';
import { WebSocket, WebSocketServer } from 'ws';
import { buildSite, BuildOptions } from './generator';

export interface ServeOptions extends BuildOptions {
  port?: number;
}

export interface DevServer {
  server: http.Server;
  watcher: FSWatcher;
  webSocketServer: WebSocketServer;
  close: () => Promise<void>;
}

const liveReloadScript = `<script>(function(){var ws=new WebSocket((location.protocol==='https:'?'wss://':'ws://')+location.host);ws.onmessage=function(event){if(event.data==='reload')location.reload();};})();</script>`;

function injectLiveReload(html: string): string {
  const closingBody = html.search(/<\/body\s*>/i);
  if (closingBody === -1) return `${html}${liveReloadScript}`;
  return `${html.slice(0, closingBody)}${liveReloadScript}${html.slice(closingBody)}`;
}

async function serveFile(outputDir: string, requestPath: string, response: http.ServerResponse): Promise<void> {
  const pathname = decodeURIComponent(requestPath.split('?')[0]);
  const relative = pathname === '/' ? 'index.html' : pathname.replace(/^\/+/, '');
  const file = path.resolve(outputDir, relative);
  if (file !== outputDir && !file.startsWith(`${outputDir}${path.sep}`)) {
    response.writeHead(403); response.end('Forbidden'); return;
  }
  try {
    const stats = await fs.stat(file);
    if (!stats.isFile()) throw new Error('Not a file');
    if (path.extname(file).toLowerCase() === '.html') {
      response.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
      response.end(injectLiveReload(await fs.readFile(file, 'utf8')));
    } else {
      response.writeHead(200);
      createReadStream(file).pipe(response);
    }
  } catch {
    response.writeHead(404); response.end('Not found');
  }
}

export async function startDevServer(options: ServeOptions = {}): Promise<DevServer> {
  const outputDir = path.resolve(options.outputDir ?? './dist');
  const contentDir = path.resolve(options.contentDir ?? './content');
  const templatesDir = path.resolve(options.templatesDir ?? './templates');
  await buildSite(options);

  const webSocketServer = new WebSocketServer({ noServer: true });
  const server = http.createServer((request, response) => {
    void serveFile(outputDir, request.url ?? '/', response);
  });
  server.on('upgrade', (request, socket, head) => {
    webSocketServer.handleUpgrade(request, socket, head, (client) => webSocketServer.emit('connection', client, request));
  });
  webSocketServer.on('connection', (client) => client.send('connected'));
  const watcher = chokidar.watch([contentDir, templatesDir], { ignoreInitial: true });
  let rebuilding = false;
  let pending = false;
  const rebuild = async (): Promise<void> => {
    if (rebuilding) { pending = true; return; }
    rebuilding = true;
    try {
      await buildSite(options);
      webSocketServer.clients.forEach((client) => { if (client.readyState === WebSocket.OPEN) client.send('reload'); });
    } catch (error) {
      console.error(error instanceof Error ? error.message : error);
    } finally {
      rebuilding = false;
      if (pending) { pending = false; void rebuild(); }
    }
  };
  watcher.on('all', () => { void rebuild(); });
  await new Promise<void>((resolve) => server.listen(options.port ?? 3000, 'localhost', resolve));
  return {
    server,
    watcher,
    webSocketServer,
    close: async () => {
      await watcher.close();
      webSocketServer.clients.forEach((client) => client.close());
      await new Promise<void>((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
      await new Promise<void>((resolve) => webSocketServer.close(() => resolve()));
    },
  };
}

export async function serveSite(options: ServeOptions = {}): Promise<void> {
  const instance = await startDevServer(options);
  const address = instance.server.address();
  const port = typeof address === 'object' && address ? address.port : options.port ?? 3000;
  console.log(`Serving ${path.resolve(options.outputDir ?? './dist')} at http://localhost:${port}`);
}
