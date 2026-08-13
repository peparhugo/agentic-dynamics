import { promises as fs } from 'node:fs';
import http, { type ServerResponse } from 'node:http';
import path from 'node:path';
import chokidar, { type FSWatcher } from 'chokidar';
import { WebSocket, WebSocketServer } from 'ws';
import { SsgEngine } from '../engine';
import type { BuildOptions, Plugin } from '../types';

export interface ServeOptions extends BuildOptions {
  host?: string;
  port?: number;
}

export interface DevServer {
  host: string;
  port: number;
  close(): Promise<void>;
}

const reloadScript = `<script>(()=>{const connect=()=>{const socket=new WebSocket((location.protocol==='https:'?'wss://':'ws://')+location.host+'/__ssg_reload');socket.onmessage=event=>{if(event.data==='reload')location.reload()};socket.onclose=()=>setTimeout(connect,1000)};connect()})()</script>`;

const contentTypes: Record<string, string> = {
  '.css': 'text/css; charset=utf-8', '.gif': 'image/gif', '.html': 'text/html; charset=utf-8',
  '.ico': 'image/x-icon', '.jpeg': 'image/jpeg', '.jpg': 'image/jpeg', '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8', '.png': 'image/png', '.svg': 'image/svg+xml',
  '.txt': 'text/plain; charset=utf-8', '.webp': 'image/webp',
};

const injectReloadScript = (html: string): string => {
  const closingBody = html.search(/<\/body\s*>/i);
  return closingBody === -1 ? `${html}${reloadScript}` : `${html.slice(0, closingBody)}${reloadScript}\n${html.slice(closingBody)}`;
};

const send = (response: ServerResponse, status: number, body: string): void => {
  response.writeHead(status, { 'Content-Type': 'text/plain; charset=utf-8' });
  response.end(body);
};

const serveFile = async (outputDir: string, request: http.IncomingMessage, response: ServerResponse): Promise<void> => {
  if (request.method !== 'GET' && request.method !== 'HEAD') {
    response.setHeader('Allow', 'GET, HEAD');
    send(response, 405, 'Method Not Allowed');
    return;
  }
  let pathname: string;
  try {
    pathname = decodeURIComponent(new URL(request.url ?? '/', 'http://localhost').pathname);
  } catch {
    send(response, 400, 'Bad Request');
    return;
  }
  const requestedPath = pathname.endsWith('/') ? `${pathname}index.html` : pathname;
  const filename = path.resolve(outputDir, `.${requestedPath}`);
  const relative = path.relative(outputDir, filename);
  if (relative.startsWith('..') || path.isAbsolute(relative)) {
    send(response, 403, 'Forbidden');
    return;
  }
  try {
    const stats = await fs.stat(filename);
    const resolvedFilename = stats.isDirectory() ? path.join(filename, 'index.html') : filename;
    let body: Buffer | string = await fs.readFile(resolvedFilename);
    const extension = path.extname(resolvedFilename).toLowerCase();
    if (extension === '.html') body = injectReloadScript(body.toString('utf8'));
    response.writeHead(200, {
      'Content-Length': Buffer.byteLength(body),
      'Content-Type': contentTypes[extension] ?? 'application/octet-stream',
    });
    response.end(request.method === 'HEAD' ? undefined : body);
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT' || (error as NodeJS.ErrnoException).code === 'ENOTDIR') {
      send(response, 404, 'Not Found');
      return;
    }
    send(response, 500, 'Internal Server Error');
  }
};

export class DevServerPlugin implements Plugin {
  readonly name = 'dev-server';

  async start(options: ServeOptions = {}): Promise<DevServer> {
    const host = options.host ?? 'localhost';
    const requestedPort = options.port ?? 3000;
    const outputDir = path.resolve(options.outputDir ?? './dist');
    const contentDir = path.resolve(options.contentDir ?? './content');
    const templateDir = path.resolve(options.templateDir ?? './templates');
    const buildOptions = { ...options, contentDir, outputDir, templateDir };
    await new SsgEngine(buildOptions).build();

    const server = http.createServer((request, response) => void serveFile(outputDir, request, response));
    const sockets = new WebSocketServer({ noServer: true });
    server.on('upgrade', (request, socket, head) => {
      if (new URL(request.url ?? '/', 'http://localhost').pathname !== '/__ssg_reload') {
        socket.destroy();
        return;
      }
      sockets.handleUpgrade(request, socket, head, (client) => sockets.emit('connection', client, request));
    });
    await new Promise<void>((resolve, reject) => {
      const onError = (error: Error): void => reject(error);
      server.once('error', onError);
      server.listen(requestedPort, host, () => {
        server.off('error', onError);
        resolve();
      });
    });

    let rebuilding = false;
    let rebuildAgain = false;
    let closed = false;
    const rebuild = async (): Promise<void> => {
      if (rebuilding) {
        rebuildAgain = true;
        return;
      }
      rebuilding = true;
      do {
        rebuildAgain = false;
        try {
          await new SsgEngine(buildOptions).build();
          for (const client of sockets.clients) if (client.readyState === WebSocket.OPEN) client.send('reload');
        } catch (error) {
          const message = error instanceof Error ? error.message : String(error);
          process.stderr.write(`Rebuild failed: ${message}\n`);
        }
      } while (rebuildAgain && !closed);
      rebuilding = false;
    };

    let watcher: FSWatcher;
    try {
      watcher = chokidar.watch([contentDir, templateDir], {
        ignoreInitial: true,
        awaitWriteFinish: { stabilityThreshold: 100, pollInterval: 20 },
      });
      watcher.on('all', () => void rebuild());
      await new Promise<void>((resolve, reject) => {
        watcher.once('ready', resolve);
        watcher.once('error', reject);
      });
    } catch (error) {
      if (watcher!) await watcher.close();
      await new Promise<void>((resolve) => server.close(() => resolve()));
      sockets.close();
      throw error;
    }

    const address = server.address();
    const port = typeof address === 'object' && address ? address.port : requestedPort;
    return {
      host,
      port,
      async close(): Promise<void> {
        closed = true;
        await watcher.close();
        for (const client of sockets.clients) client.terminate();
        await new Promise<void>((resolve, reject) => {
          sockets.close();
          server.close((error) => error ? reject(error) : resolve());
        });
      },
    };
  }
}
