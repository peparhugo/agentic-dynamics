import { createReadStream } from 'node:fs';
import { readFile, stat } from 'node:fs/promises';
import { createServer, IncomingMessage, ServerResponse } from 'node:http';
import path from 'node:path';
import chokidar from 'chokidar';
import { WebSocketServer } from 'ws';
import { buildSite, type BuildOptions } from '../generator';
import type { Plugin, PluginContext } from '../plugin';

export interface DevServerOptions extends BuildOptions {
  port?: number;
}

export interface DevServer {
  port: number;
  close(): Promise<void>;
}

const reloadScript = `<script>(() => { const socket = new WebSocket('ws://' + location.host + '/__ssg_reload'); socket.addEventListener('message', () => location.reload()); })();</script>`;

function injectReloadScript(html: string): string {
  return /<\/body\s*>/i.test(html) ? html.replace(/<\/body\s*>/i, `${reloadScript}</body>`) : `${html}${reloadScript}`;
}

function contentType(file: string): string {
  if (file.endsWith('.html')) return 'text/html; charset=utf-8';
  if (file.endsWith('.css')) return 'text/css; charset=utf-8';
  if (file.endsWith('.js')) return 'text/javascript; charset=utf-8';
  if (file.endsWith('.json')) return 'application/json; charset=utf-8';
  if (file.endsWith('.svg')) return 'image/svg+xml';
  return 'application/octet-stream';
}

async function serveFile(request: IncomingMessage, response: ServerResponse, outputDir: string): Promise<void> {
  if (request.method !== 'GET' && request.method !== 'HEAD') {
    response.writeHead(405, { Allow: 'GET, HEAD' }).end();
    return;
  }
  let pathname: string;
  try {
    pathname = decodeURIComponent(new URL(request.url ?? '/', 'http://localhost').pathname);
  } catch {
    response.writeHead(400).end();
    return;
  }
  const requested = pathname === '/' ? 'index.html' : pathname.replace(/^\/+/, '');
  const file = path.resolve(outputDir, requested);
  if (file !== outputDir && !file.startsWith(`${outputDir}${path.sep}`)) {
    response.writeHead(403).end();
    return;
  }
  try {
    const info = await stat(file);
    if (!info.isFile()) throw new Error('Not a file');
    response.writeHead(200, { 'Content-Type': contentType(file) });
    if (request.method === 'HEAD') response.end();
    else if (file.endsWith('.html')) response.end(injectReloadScript(await readFile(file, 'utf8')));
    else createReadStream(file).pipe(response);
  } catch {
    response.writeHead(404).end('Not found');
  }
}

export class DevServerPlugin implements Plugin, DevServer {
  port = 0;
  private readonly options: DevServerOptions;
  private closeServer?: () => Promise<void>;

  constructor(options: DevServerOptions = {}) {
    this.options = options;
  }

  async onStart(context: PluginContext): Promise<void> {
    await buildSite({ contentDir: context.contentDir, templatesDir: context.templatesDir, outputDir: context.outputDir, plugins: this.options.plugins });
    const server = createServer((request, response) => { void serveFile(request, response, context.outputDir); });
    const sockets = new WebSocketServer({ noServer: true });
    server.on('upgrade', (request, socket, head) => {
      if (new URL(request.url ?? '/', 'http://localhost').pathname !== '/__ssg_reload') {
        socket.destroy();
        return;
      }
      sockets.handleUpgrade(request, socket, head, (webSocket) => sockets.emit('connection', webSocket, request));
    });
    let rebuilding = false;
    let rebuildQueued = false;
    const rebuild = async (): Promise<void> => {
      if (rebuilding) {
        rebuildQueued = true;
        return;
      }
      rebuilding = true;
      try {
        await buildSite({ contentDir: context.contentDir, templatesDir: context.templatesDir, outputDir: context.outputDir, plugins: this.options.plugins });
        for (const client of sockets.clients) client.send('reload');
      } catch (error) {
        process.stderr.write(`Rebuild failed: ${error instanceof Error ? error.message : String(error)}\n`);
      } finally {
        rebuilding = false;
        if (rebuildQueued) {
          rebuildQueued = false;
          void rebuild();
        }
      }
    };
    const watcher = chokidar.watch([context.contentDir, context.templatesDir], { ignoreInitial: true });
    watcher.on('all', () => { void rebuild(); });
    await new Promise<void>((resolve) => watcher.once('ready', resolve));
    await new Promise<void>((resolve, reject) => {
      server.once('error', reject);
      server.listen(this.options.port ?? 3000, 'localhost', () => {
        server.off('error', reject);
        resolve();
      });
    });
    const address = server.address();
    if (!address || typeof address === 'string') throw new Error('Could not determine development server port');
    this.port = address.port;
    this.closeServer = async () => {
      await watcher.close();
      for (const client of sockets.clients) client.close();
      await new Promise<void>((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
      sockets.close();
    };
  }

  async close(): Promise<void> {
    await this.closeServer?.();
  }
}
