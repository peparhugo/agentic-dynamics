import { promises as fs } from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { WebSocketServer, WebSocket } from 'ws';
import chokidar, { FSWatcher } from 'chokidar';
import { buildSite, SiteOptions } from './generator';

export interface DevServerOptions extends SiteOptions {
  port?: number;
  host?: string;
}

export interface DevServer {
  server: http.Server;
  watcher: FSWatcher;
  port: number;
  close(): Promise<void>;
}

const reloadScript = `<script>(function(){var socket=new WebSocket((location.protocol==='https:'?'wss://':'ws://')+location.host);socket.onmessage=function(event){if(event.data==='reload')location.reload()};socket.onclose=function(){setTimeout(function(){location.reload()},1000)}})();</script>`;

function contentType(file: string): string {
  return {
    '.css': 'text/css; charset=utf-8',
    '.html': 'text/html; charset=utf-8',
    '.js': 'text/javascript; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.svg': 'image/svg+xml',
  }[path.extname(file).toLowerCase()] ?? 'application/octet-stream';
}

function withReloadScript(html: string): string {
  const closingBody = html.search(/<\/body\s*>/i);
  return closingBody === -1 ? `${html}${reloadScript}` : `${html.slice(0, closingBody)}${reloadScript}${html.slice(closingBody)}`;
}

async function serveFile(outputDir: string, requestPath: string): Promise<{ body: Buffer; type: string } | undefined> {
  const decoded = decodeURIComponent(requestPath.split('?')[0]);
  const relative = decoded === '/' ? 'index.html' : decoded.replace(/^\/+/, '');
  const root = path.resolve(outputDir);
  const file = path.resolve(root, relative);
  if (file !== root && !file.startsWith(`${root}${path.sep}`)) return undefined;
  try {
    const stat = await fs.stat(file);
    if (!stat.isFile()) return undefined;
    let body = await fs.readFile(file);
    if (path.extname(file).toLowerCase() === '.html') body = Buffer.from(withReloadScript(body.toString('utf8')));
    return { body, type: contentType(file) };
  } catch {
    return undefined;
  }
}

export async function startDevServer(options: DevServerOptions = {}): Promise<DevServer> {
  const outputDir = path.resolve(options.outputDir ?? './dist');
  const contentDir = path.resolve(options.contentDir ?? './content');
  const templatesDir = path.resolve(options.templatesDir ?? './templates');
  const host = options.host ?? 'localhost';
  const port = options.port ?? 3000;
  await buildSite({ ...options, contentDir, outputDir, templatesDir });

  const server = http.createServer(async (request, response) => {
    if (request.method !== 'GET' && request.method !== 'HEAD') {
      response.writeHead(405).end();
      return;
    }
    try {
      const result = await serveFile(outputDir, request.url ?? '/');
      if (!result) {
        response.writeHead(404).end('Not found');
        return;
      }
      response.writeHead(200, { 'Content-Type': result.type, 'Content-Length': result.body.length });
      if (request.method === 'GET') response.end(result.body);
      else response.end();
    } catch {
      response.writeHead(400).end('Bad request');
    }
  });
  const sockets = new Set<WebSocket>();
  const webSocketServer = new WebSocketServer({ server });
  webSocketServer.on('connection', (socket) => {
    sockets.add(socket);
    socket.on('close', () => sockets.delete(socket));
  });
  webSocketServer.on('close', () => sockets.clear());

  let buildQueue = Promise.resolve();
  const rebuild = (): void => {
    buildQueue = buildQueue.then(async () => {
      try {
        await buildSite({ ...options, contentDir, outputDir, templatesDir });
        for (const socket of sockets) if (socket.readyState === WebSocket.OPEN) socket.send('reload');
      } catch (error) {
        console.error(`Build failed: ${error instanceof Error ? error.message : error}`);
      }
    });
  };
  const watcher = chokidar.watch([contentDir, templatesDir], { ignoreInitial: true });
  watcher.on('add', rebuild).on('change', rebuild).on('unlink', rebuild);

  await new Promise<void>((resolve, reject) => {
    server.once('error', reject);
    server.listen(port, host, () => {
      server.removeListener('error', reject);
      resolve();
    });
  });
  const address = server.address();
  const actualPort = typeof address === 'object' && address ? address.port : port;
  return {
    server, watcher, port: actualPort,
    async close(): Promise<void> {
      await watcher.close();
      await buildQueue;
      for (const socket of sockets) socket.terminate();
      await new Promise<void>((resolve) => webSocketServer.close(() => resolve()));
      await new Promise<void>((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
    },
  };
}
