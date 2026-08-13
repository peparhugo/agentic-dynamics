import { createReadStream, promises as fs } from 'node:fs';
import { createServer, type Server } from 'node:http';
import path from 'node:path';
import chokidar, { type FSWatcher } from 'chokidar';
import { WebSocket, WebSocketServer } from 'ws';
import { buildSite } from './engine';
import type { BuildOptions, Plugin, PluginContext } from './types';

export interface ServeOptions extends BuildOptions {
  port?: number;
}

export interface DevServer {
  port: number;
  close(): Promise<void>;
}

const LIVE_RELOAD_SCRIPT = `<script>
(() => {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const socket = new WebSocket(protocol + '//' + location.host);
  socket.addEventListener('message', (event) => {
    if (event.data === 'reload') location.reload();
  });
})();
</script>`;

const CONTENT_TYPES: Record<string, string> = {
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
  '.webp': 'image/webp',
};

function injectLiveReload(html: string): string {
  const bodyEnd = html.search(/<\/body\s*>/i);
  if (bodyEnd === -1) return `${html}\n${LIVE_RELOAD_SCRIPT}\n`;
  return `${html.slice(0, bodyEnd)}${LIVE_RELOAD_SCRIPT}\n${html.slice(bodyEnd)}`;
}

async function requestedFile(outputDir: string, requestUrl: string): Promise<string | null> {
  let pathname: string;
  try {
    pathname = decodeURIComponent(new URL(requestUrl, 'http://localhost').pathname);
  } catch {
    return null;
  }

  const relative = pathname.replace(/^\/+/, '') || 'index.html';
  let file = path.resolve(outputDir, relative);
  const outputRoot = `${path.resolve(outputDir)}${path.sep}`;
  if (file !== path.resolve(outputDir) && !file.startsWith(outputRoot)) return null;

  const stat = await fs.stat(file).catch(() => null);
  if (stat?.isDirectory()) file = path.join(file, 'index.html');
  return await fs.stat(file).then((entry) => entry.isFile() ? file : null).catch(() => null);
}

function listen(server: Server, port: number): Promise<number> {
  return new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(port, 'localhost', () => {
      server.off('error', reject);
      const address = server.address();
      resolve(typeof address === 'object' && address ? address.port : port);
    });
  });
}

export class DevServerPlugin implements Plugin {
  private readonly server: Server;
  private readonly sockets: WebSocketServer;
  private watcher?: FSWatcher;
  private started = false;
  private building = false;
  private rebuildPending = false;
  private context?: PluginContext;
  private selectedPort?: number;

  constructor(private readonly options: ServeOptions = {}) {
    this.server = createServer(async (request, response) => {
      if (request.method !== 'GET' && request.method !== 'HEAD') {
        response.writeHead(405, { Allow: 'GET, HEAD' }).end();
        return;
      }

      const file = await requestedFile(this.context?.outputDir ?? path.resolve(this.options.outputDir ?? './dist'), request.url ?? '/');
      if (!file) {
        response.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' }).end('Not found');
        return;
      }

      const contentType = CONTENT_TYPES[path.extname(file).toLowerCase()] ?? 'application/octet-stream';
      if (contentType.startsWith('text/html')) {
        const html = injectLiveReload(await fs.readFile(file, 'utf8'));
        response.writeHead(200, { 'Content-Type': contentType, 'Content-Length': Buffer.byteLength(html) });
        response.end(request.method === 'HEAD' ? undefined : html);
        return;
      }

      const size = (await fs.stat(file)).size;
      response.writeHead(200, { 'Content-Type': contentType, 'Content-Length': size });
      if (request.method === 'HEAD') response.end();
      else createReadStream(file).pipe(response);
    });
    this.sockets = new WebSocketServer({ server: this.server });
  }

  async afterBuild(context: PluginContext): Promise<void> {
    this.context = context;
    if (this.started) {
      setImmediate(() => {
        for (const client of this.sockets.clients) {
          if (client.readyState === WebSocket.OPEN) client.send('reload');
        }
      });
      return;
    }
    this.started = true;
    this.watcher = chokidar.watch([context.contentDir, context.templatesDir], { ignoreInitial: true });
    const ready = new Promise<void>((resolve) => this.watcher?.once('ready', resolve));
    this.watcher.on('all', () => void this.rebuild());
    await ready;
    this.selectedPort = await listen(this.server, this.options.port ?? 3000);
  }

  private async rebuild(): Promise<void> {
    if (this.building) {
      this.rebuildPending = true;
      return;
    }
    this.building = true;
    do {
      this.rebuildPending = false;
      try {
        const pages = await buildSite({
          ...this.options,
          contentDir: this.context?.contentDir,
          outputDir: this.context?.outputDir,
          templatesDir: this.context?.templatesDir,
          plugins: [...(this.options.plugins ?? []), this],
        });
        console.log(`Rebuilt ${pages.length} page${pages.length === 1 ? '' : 's'}.`);
      } catch (error) {
        console.error(`Rebuild failed: ${error instanceof Error ? error.message : String(error)}`);
      }
    } while (this.rebuildPending);
    this.building = false;
  }

  get port(): number {
    if (this.selectedPort === undefined) throw new Error('Development server has not started');
    return this.selectedPort;
  }

  async close(): Promise<void> {
    await this.watcher?.close();
    for (const client of this.sockets.clients) client.terminate();
    if (!this.server.listening) return;
    await new Promise<void>((resolve, reject) => {
      this.sockets.close(() => this.server.close((error) => error ? reject(error) : resolve()));
    });
  }
}

export async function serveSite(options: ServeOptions = {}): Promise<DevServer> {
  const plugin = new DevServerPlugin(options);
  try {
    await buildSite({ ...options, plugins: [...(options.plugins ?? []), plugin] });
    return plugin;
  } catch (error) {
    await plugin.close().catch(() => undefined);
    throw error;
  }
}
