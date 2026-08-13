import { promises as fs } from 'node:fs';
import { createServer, type Server as HttpServer, type ServerResponse } from 'node:http';
import path from 'node:path';
import chokidar, { type FSWatcher } from 'chokidar';
import { WebSocket, WebSocketServer } from 'ws';
import type { BuildContext, Plugin } from '../plugin.js';

const reloadScript = `<script>(()=>{const connect=()=>{const socket=new WebSocket('ws://'+location.host+'/__ssg_reload');socket.onmessage=event=>{if(event.data==='reload')location.reload()};socket.onclose=()=>setTimeout(connect,500)};connect()})()</script>`;
const contentTypes: Record<string, string> = {
  '.css': 'text/css; charset=utf-8', '.gif': 'image/gif', '.html': 'text/html; charset=utf-8',
  '.ico': 'image/x-icon', '.jpeg': 'image/jpeg', '.jpg': 'image/jpeg', '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8', '.png': 'image/png', '.svg': 'image/svg+xml',
  '.txt': 'text/plain; charset=utf-8', '.webp': 'image/webp'
};

function send(response: ServerResponse, status: number, body: string): void {
  response.writeHead(status, { 'content-type': 'text/plain; charset=utf-8' });
  response.end(body);
}

function injectReloadScript(html: string): string {
  const closingBody = html.toLowerCase().lastIndexOf('</body>');
  return closingBody === -1 ? `${html}${reloadScript}`
    : `${html.slice(0, closingBody)}${reloadScript}\n${html.slice(closingBody)}`;
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
    response.writeHead(200, { 'content-length': body.byteLength,
      'content-type': contentTypes[extension] ?? 'application/octet-stream' });
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
  return new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
}

export class DevServerPlugin implements Plugin {
  readonly name = 'dev-server';
  private server?: HttpServer;
  private sockets?: WebSocketServer;
  private watcher?: FSWatcher;
  private rebuild?: () => Promise<void>;
  private listeningPort?: number;

  constructor(private readonly port = 3000) {}

  setRebuild(rebuild: () => Promise<void>): void {
    this.rebuild = rebuild;
  }

  getPort(): number {
    if (this.listeningPort === undefined) throw new Error('Development server has not started');
    return this.listeningPort;
  }

  async afterBuild(context: BuildContext): Promise<void> {
    if (this.server) {
      for (const client of this.sockets?.clients ?? []) {
        if (client.readyState === WebSocket.OPEN) client.send('reload');
      }
      return;
    }
    const outputDir = context.options.outputDir;
    this.server = createServer((request, response) => {
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
    this.sockets = new WebSocketServer({ server: this.server, path: '/__ssg_reload' });
    try {
      await new Promise<void>((resolve, reject) => {
        const onError = (error: Error): void => reject(error);
        this.server?.once('error', onError);
        this.server?.listen(this.port, 'localhost', () => {
          this.server?.off('error', onError);
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
            await this.rebuild?.();
          } catch (error) {
            process.stderr.write(`Rebuild failed: ${error instanceof Error ? error.message : String(error)}\n`);
          }
        } while (rebuildQueued);
        rebuilding = false;
      };
      this.watcher = chokidar.watch([context.options.contentDir, context.options.templatesDir], { ignoreInitial: true });
      this.watcher.on('all', () => void rebuild());
      await new Promise<void>((resolve, reject) => {
        this.watcher?.once('ready', resolve);
        this.watcher?.once('error', reject);
      });
    } catch (error) {
      this.sockets.close();
      if (this.server.listening) await closeHttpServer(this.server);
      throw error;
    }
    const address = this.server.address();
    this.listeningPort = typeof address === 'object' && address ? address.port : this.port;
  }

  async onEnd(): Promise<void> {
    await this.watcher?.close();
    for (const client of this.sockets?.clients ?? []) client.terminate();
    this.sockets?.close();
    if (this.server?.listening) await closeHttpServer(this.server);
    this.server = undefined;
  }
}
