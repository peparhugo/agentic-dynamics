import { createReadStream, promises as fs } from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import chokidar, { FSWatcher } from 'chokidar';
import { buildSite } from './generator';
import { DevServerOptions } from './types';
import { WebSocketServer, WebSocket } from 'ws';
import { Plugin, PluginContext } from './plugin';

const LIVE_RELOAD_SCRIPT = `<script>(function(){var ws=new WebSocket((location.protocol==='https:'?'wss://':'ws://')+location.host);ws.onmessage=function(event){if(event.data==='reload')location.reload();};ws.onclose=function(){setTimeout(function(){location.reload();},1000);};})();</script>`;

export interface DevServer {
  server: http.Server;
  watcher: FSWatcher;
  port: number;
  close(): Promise<void>;
}

/** Starts the existing development server as part of a plugin lifecycle. */
export class DevServerPlugin implements Plugin {
  private devServer?: DevServer;

  constructor(private readonly options: DevServerOptions = {}) {}

  async onStart(context: PluginContext): Promise<void> {
    this.devServer = await startDevServer({ ...context.options, ...this.options });
  }

  async onEnd(): Promise<void> {
    await this.devServer?.close();
  }

  get server(): DevServer | undefined {
    return this.devServer;
  }
}

function contentType(filePath: string): string {
  const types: Record<string, string> = {
    '.html': 'text/html; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.js': 'text/javascript; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.svg': 'image/svg+xml',
  };
  return types[path.extname(filePath).toLowerCase()] || 'application/octet-stream';
}

function requestedFile(root: string, requestUrl: string): string | undefined {
  let pathname: string;
  try {
    pathname = decodeURIComponent(new URL(requestUrl, 'http://localhost').pathname);
  } catch {
    return undefined;
  }
  const relative = pathname === '/' ? 'index.html' : pathname.replace(/^\/+/, '');
  const filePath = path.resolve(root, relative);
  if (filePath !== root && !filePath.startsWith(`${root}${path.sep}`)) return undefined;
  return filePath;
}

function serveFile(root: string, request: http.IncomingMessage, response: http.ServerResponse): void {
  const filePath = requestedFile(root, request.url || '/');
  if (!filePath) {
    response.writeHead(400).end('Bad request');
    return;
  }
  fs.stat(filePath).then((stat) => {
    if (!stat.isFile()) throw new Error('Not a file');
    response.setHeader('Content-Type', contentType(filePath));
    if (path.extname(filePath).toLowerCase() === '.html') {
      return fs.readFile(filePath, 'utf8').then((html) => {
        const injected = html.includes('</body>') ? html.replace('</body>', `${LIVE_RELOAD_SCRIPT}</body>`) : `${html}${LIVE_RELOAD_SCRIPT}`;
        response.end(injected);
      });
    }
    return new Promise<void>((resolve, reject) => {
      createReadStream(filePath).on('error', reject).on('end', resolve).pipe(response);
    });
  }).catch(() => response.writeHead(404).end('Not found'));
}

export async function startDevServer(options: DevServerOptions = {}): Promise<DevServer> {
  const contentDir = options.contentDir || './content';
  const templatesDir = options.templatesDir || './templates';
  const outputDir = path.resolve(options.outputDir || './dist');
  await buildSite({ ...options, outputDir });

  const clients = new Set<WebSocket>();
  const webSocketServer = new WebSocketServer({ noServer: true });
  webSocketServer.on('connection', (client) => {
    clients.add(client);
    client.on('close', () => clients.delete(client));
  });
  const server = http.createServer((request, response) => serveFile(outputDir, request, response));
  server.on('upgrade', (request, socket, head) => {
    webSocketServer.handleUpgrade(request, socket, head, (client) => webSocketServer.emit('connection', client, request));
  });

  let rebuilding: Promise<void> | undefined;
  let rebuildQueued = false;
  const rebuild = async (): Promise<void> => {
    if (rebuilding) {
      rebuildQueued = true;
      return rebuilding;
    }
    rebuilding = (async () => {
      do {
        rebuildQueued = false;
        await buildSite({ ...options, outputDir });
        for (const client of clients) if (client.readyState === WebSocket.OPEN) client.send('reload');
      } while (rebuildQueued);
    })().finally(() => { rebuilding = undefined; });
    return rebuilding;
  };
  const watcher = chokidar.watch([contentDir, templatesDir], { ignoreInitial: true });
  watcher.on('add', rebuild).on('change', rebuild).on('unlink', rebuild).on('addDir', rebuild).on('unlinkDir', rebuild);

  const port = options.port || 3000;
  await new Promise<void>((resolve, reject) => {
    server.once('error', reject);
    server.listen(port, 'localhost', () => {
      server.removeListener('error', reject);
      resolve();
    });
  });
  return {
    server,
    watcher,
    port,
    close: async () => {
      await watcher.close();
      for (const client of clients) client.close();
      await new Promise<void>((resolve) => server.close(() => resolve()));
      webSocketServer.close();
    },
  };
}
