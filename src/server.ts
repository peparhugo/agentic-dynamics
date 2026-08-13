import { promises as fs } from 'node:fs';
import http, { IncomingMessage, ServerResponse } from 'node:http';
import path from 'node:path';
import chokidar, { FSWatcher } from 'chokidar';
import { WebSocket, WebSocketServer } from 'ws';
import { SsgEngine } from './engine';
import { BuildOptions, Plugin, PluginContext } from './plugin';

export interface ServeOptions extends BuildOptions {
  port?: number;
}

export interface DevServer {
  port: number;
  close(): Promise<void>;
}

const liveReloadScript = `<script>
(() => {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const socket = new WebSocket(protocol + '//' + location.host + '/__ssg_live_reload');
  socket.addEventListener('message', (event) => {
    if (event.data === 'reload') location.reload();
  });
})();
</script>`;

const contentTypes: Record<string, string> = {
  '.css': 'text/css; charset=utf-8', '.gif': 'image/gif', '.html': 'text/html; charset=utf-8',
  '.ico': 'image/x-icon', '.jpeg': 'image/jpeg', '.jpg': 'image/jpeg', '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8', '.png': 'image/png', '.svg': 'image/svg+xml; charset=utf-8',
  '.webp': 'image/webp'
};

function injectLiveReload(html: string): string {
  const closingBody = /<\/body\s*>/i;
  return closingBody.test(html) ? html.replace(closingBody, `${liveReloadScript}\n</body>`) : `${html}\n${liveReloadScript}`;
}

async function resolveFile(request: IncomingMessage, outputDir: string): Promise<string | undefined> {
  let pathname: string;
  try {
    pathname = decodeURIComponent(new URL(request.url ?? '/', 'http://localhost').pathname);
  } catch {
    return undefined;
  }
  const relative = pathname === '/' ? 'index.html' : pathname.replace(/^\/+/, '');
  const root = path.resolve(outputDir);
  let candidate = path.resolve(root, relative);
  if (candidate !== root && !candidate.startsWith(`${root}${path.sep}`)) return undefined;
  try {
    const stats = await fs.stat(candidate);
    if (stats.isDirectory()) candidate = path.join(candidate, 'index.html');
    return (await fs.stat(candidate)).isFile() ? candidate : undefined;
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return undefined;
    throw error;
  }
}

async function serveFile(request: IncomingMessage, response: ServerResponse, outputDir: string): Promise<void> {
  const file = await resolveFile(request, outputDir);
  if (!file) {
    response.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
    response.end('Not found');
    return;
  }
  const extension = path.extname(file).toLowerCase();
  const data = await fs.readFile(file);
  const body = extension === '.html' ? injectLiveReload(data.toString('utf8')) : data;
  response.writeHead(200, { 'Content-Type': contentTypes[extension] ?? 'application/octet-stream' });
  response.end(request.method === 'HEAD' ? undefined : body);
}

export class DevServerPlugin implements Plugin {
  readonly name = 'dev-server';
  private server?: http.Server;
  private sockets?: WebSocketServer;
  private watcher?: FSWatcher;
  private rebuilding = false;
  private rebuildPending = false;
  private context?: PluginContext;
  port: number;

  constructor(private readonly requestedPort = 3000) {
    this.port = requestedPort;
  }

  async onStart(context: PluginContext): Promise<void> {
    this.context = context;
    const server = http.createServer((request, response) => {
      void serveFile(request, response, context.options.outputDir).catch((error: unknown) => {
        const message = error instanceof Error ? error.message : String(error);
        response.writeHead(500, { 'Content-Type': 'text/plain; charset=utf-8' });
        response.end(`Server error: ${message}`);
      });
    });
    this.server = server;
    this.sockets = new WebSocketServer({ server, path: '/__ssg_live_reload' });
    try {
      await context.build();
      await new Promise<void>((resolve, reject) => {
        server.once('error', reject);
        server.listen(this.requestedPort, 'localhost', () => {
          server.off('error', reject);
          resolve();
        });
      });
      this.watcher = chokidar.watch([context.options.contentDir, context.options.templatesDir], { ignoreInitial: true });
      this.watcher.on('all', () => void this.rebuild());
      await new Promise<void>((resolve, reject) => {
        this.watcher?.once('ready', resolve);
        this.watcher?.once('error', reject);
      });
      const address = server.address();
      this.port = typeof address === 'object' && address ? address.port : this.requestedPort;
      process.stdout.write(`Serving ${context.options.outputDir} at http://localhost:${this.port}\n`);
    } catch (error) {
      await this.closeResources();
      throw error;
    }
  }

  private async rebuild(): Promise<void> {
    this.rebuildPending = true;
    if (this.rebuilding) return;
    this.rebuilding = true;
    while (this.rebuildPending) {
      this.rebuildPending = false;
      try {
        const pages = await this.context?.build() ?? [];
        process.stdout.write(`Rebuilt ${pages.length} page${pages.length === 1 ? '' : 's'}.\n`);
        for (const client of this.sockets?.clients ?? []) {
          if (client.readyState === WebSocket.OPEN) client.send('reload');
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        process.stderr.write(`Rebuild failed: ${message}\n`);
      }
    }
    this.rebuilding = false;
  }

  private async closeResources(): Promise<void> {
    await this.watcher?.close();
    for (const client of this.sockets?.clients ?? []) client.terminate();
    if (this.sockets) await new Promise<void>((resolve) => this.sockets?.close(() => resolve()));
    if (this.server?.listening) await new Promise<void>((resolve) => this.server?.close(() => resolve()));
  }

  async onEnd(): Promise<void> {
    await this.closeResources();
  }
}

export async function serveSite(options: ServeOptions = {}): Promise<DevServer> {
  const plugin = new DevServerPlugin(options.port ?? 3000);
  const buildOptions: BuildOptions = { ...options };
  delete (buildOptions as ServeOptions).port;
  const engine = new SsgEngine(buildOptions, [plugin]);
  await engine.start();
  return { port: plugin.port, close: () => engine.stop() };
}
