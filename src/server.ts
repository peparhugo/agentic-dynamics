import { promises as fs } from 'node:fs';
import { createServer, type Server as HttpServer, type ServerResponse } from 'node:http';
import path from 'node:path';
import chokidar, { type FSWatcher } from 'chokidar';
import { WebSocket, WebSocketServer } from 'ws';
import { buildSite, type BuildOptions } from './index.js';

export interface ServeOptions extends BuildOptions {
  port?: number;
}

export interface DevServer {
  port: number;
  close(): Promise<void>;
}

const reloadScript = `<script>(()=>{const connect=()=>{const socket=new WebSocket('ws://'+location.host+'/__ssg_reload');socket.onmessage=event=>{if(event.data==='reload')location.reload()};socket.onclose=()=>setTimeout(connect,500)};connect()})()</script>`;

const contentTypes: Record<string, string> = {
  '.css': 'text/css; charset=utf-8',
  '.gif': 'image/gif',
  '.html': 'text/html; charset=utf-8',
  '.ico': 'image/x-icon',
  '.jpeg': 'image/jpeg',
  '.jpg': 'image/jpeg',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.svg': 'image/svg+xml',
  '.txt': 'text/plain; charset=utf-8',
  '.webp': 'image/webp'
};

function injectReloadScript(html: string): string {
  const closingBody = html.toLowerCase().lastIndexOf('</body>');
  return closingBody === -1
    ? `${html}${reloadScript}`
    : `${html.slice(0, closingBody)}${reloadScript}\n${html.slice(closingBody)}`;
}

function send(response: ServerResponse, status: number, body: string): void {
  response.writeHead(status, { 'content-type': 'text/plain; charset=utf-8' });
  response.end(body);
}

async function serveFile(outputDir: string, requestPath: string, response: ServerResponse, headOnly: boolean): Promise<void> {
  let decodedPath: string;
  try {
    decodedPath = decodeURIComponent(requestPath);
  } catch {
    send(response, 400, 'Bad Request');
    return;
  }

  const relativePath = decodedPath.endsWith('/') ? `${decodedPath}index.html` : decodedPath;
  const filePath = path.resolve(outputDir, `.${relativePath}`);
  const relative = path.relative(outputDir, filePath);
  if (relative === '..' || relative.startsWith(`..${path.sep}`) || path.isAbsolute(relative)) {
    send(response, 403, 'Forbidden');
    return;
  }

  try {
    const stat = await fs.stat(filePath);
    if (!stat.isFile()) {
      send(response, 404, 'Not Found');
      return;
    }
    const extension = path.extname(filePath).toLowerCase();
    const source = await fs.readFile(filePath);
    const body = extension === '.html' ? Buffer.from(injectReloadScript(source.toString('utf8'))) : source;
    response.writeHead(200, {
      'content-length': body.byteLength,
      'content-type': contentTypes[extension] ?? 'application/octet-stream'
    });
    response.end(headOnly ? undefined : body);
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') {
      send(response, 404, 'Not Found');
      return;
    }
    throw error;
  }
}

function closeHttpServer(server: HttpServer): Promise<void> {
  return new Promise((resolve, reject) => {
    server.close((error) => error ? reject(error) : resolve());
  });
}

export async function startDevServer(options: ServeOptions = {}): Promise<DevServer> {
  const port = options.port ?? 3000;
  const contentDir = path.resolve(options.contentDir ?? 'content');
  const templatesDir = path.resolve(options.templatesDir ?? 'templates');
  const outputDir = path.resolve(options.outputDir ?? 'dist');
  const buildOptions = { ...options, contentDir, templatesDir, outputDir };

  await buildSite(buildOptions);

  const server = createServer((request, response) => {
    if (request.method !== 'GET' && request.method !== 'HEAD') {
      send(response, 405, 'Method Not Allowed');
      return;
    }
    const requestPath = new URL(request.url ?? '/', 'http://localhost').pathname;
    void serveFile(outputDir, requestPath, response, request.method === 'HEAD').catch(() => {
      if (!response.headersSent) send(response, 500, 'Internal Server Error');
      else response.destroy();
    });
  });
  const sockets = new WebSocketServer({ server, path: '/__ssg_reload' });
  let watcher: FSWatcher | undefined;

  try {
    await new Promise<void>((resolve, reject) => {
      const onError = (error: Error) => reject(error);
      server.once('error', onError);
      server.listen(port, 'localhost', () => {
        server.off('error', onError);
        resolve();
      });
    });

    let rebuilding = false;
    let rebuildQueued = false;
    const rebuild = async (): Promise<void> => {
      if (rebuilding) {
        rebuildQueued = true;
        return;
      }
      rebuilding = true;
      do {
        rebuildQueued = false;
        try {
          await buildSite(buildOptions);
          for (const client of sockets.clients) {
            if (client.readyState === WebSocket.OPEN) client.send('reload');
          }
        } catch (error) {
          process.stderr.write(`Rebuild failed: ${error instanceof Error ? error.message : String(error)}\n`);
        }
      } while (rebuildQueued);
      rebuilding = false;
    };
    watcher = chokidar.watch([contentDir, templatesDir], { ignoreInitial: true });
    watcher.on('all', () => void rebuild());
    await new Promise<void>((resolve, reject) => {
      watcher?.once('ready', resolve);
      watcher?.once('error', reject);
    });
  } catch (error) {
    sockets.close();
    if (server.listening) await closeHttpServer(server);
    throw error;
  }

  const address = server.address();
  const listeningPort = typeof address === 'object' && address ? address.port : port;
  return {
    port: listeningPort,
    async close(): Promise<void> {
      await watcher?.close();
      for (const client of sockets.clients) client.terminate();
      sockets.close();
      await closeHttpServer(server);
    }
  };
}
