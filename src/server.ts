import { promises as fs } from 'node:fs';
import { createServer, type Server } from 'node:http';
import path from 'node:path';
import chokidar, { type FSWatcher } from 'chokidar';
import { WebSocket, WebSocketServer } from 'ws';
import { createBuildEngine } from './core';
import type { BuildOptions, Plugin, PluginContext } from './plugin';

export interface ServeOptions extends BuildOptions {
  port?: number;
  host?: string;
}

export interface DevServer {
  port: number;
  close(): Promise<void>;
}

const liveReloadScript = `<script>
(() => {
  const socket = new WebSocket(` + "`ws://${location.host}`" + `);
  socket.addEventListener('message', (event) => {
    if (event.data === 'reload') location.reload();
  });
})();
</script>`;

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

function injectLiveReload(html: string): string {
  const closingBody = /<\/body\s*>/i;
  return closingBody.test(html)
    ? html.replace(closingBody, `${liveReloadScript}\n</body>`)
    : `${html}\n${liveReloadScript}\n`;
}

function requestFile(outputDir: string, requestUrl: string): string | undefined {
  let pathname: string;
  try {
    pathname = decodeURIComponent(new URL(requestUrl, 'http://localhost').pathname);
  } catch {
    return undefined;
  }
  const relative = pathname.endsWith('/') ? `${pathname}index.html` : pathname;
  const file = path.resolve(outputDir, `.${relative}`);
  const withinOutput = path.relative(outputDir, file);
  return withinOutput.startsWith(`..${path.sep}`) || path.isAbsolute(withinOutput) ? undefined : file;
}

export class DevServerPlugin implements Plugin {
  readonly name = 'dev-server';
  port: number;
  private readonly host: string;
  private server?: Server;
  private sockets?: WebSocketServer;
  private watcher?: FSWatcher;
  private initialized = false;
  private rebuild = Promise.resolve();

  constructor(options: Pick<ServeOptions, 'port' | 'host'> = {}) {
    this.port = options.port ?? 3000;
    this.host = options.host ?? 'localhost';
  }

  async afterBuild(context: PluginContext): Promise<void> {
    if (this.initialized) {
      for (const client of this.sockets?.clients ?? []) {
        if (client.readyState === WebSocket.OPEN) client.send('reload');
      }
      return;
    }
    this.initialized = true;
    const outputDir = context.options.outputDir;
    this.server = createServer(async (request, response) => {
      if (request.method !== 'GET' && request.method !== 'HEAD') {
        response.writeHead(405, { Allow: 'GET, HEAD' }).end();
        return;
      }
      const file = requestFile(outputDir, request.url ?? '/');
      if (!file) {
        response.writeHead(400).end('Bad request');
        return;
      }
      try {
        let data = await fs.readFile(file);
        const extension = path.extname(file).toLowerCase();
        if (extension === '.html') data = Buffer.from(injectLiveReload(data.toString('utf8')));
        response.writeHead(200, {
          'Content-Type': contentTypes[extension] ?? 'application/octet-stream',
          'Content-Length': data.byteLength,
          'Cache-Control': 'no-store'
        });
        response.end(request.method === 'HEAD' ? undefined : data);
      } catch (error) {
        const status = (error as NodeJS.ErrnoException).code === 'ENOENT' ? 404 : 500;
        response.writeHead(status).end(status === 404 ? 'Not found' : 'Server error');
      }
    });
    this.sockets = new WebSocketServer({ server: this.server });
    this.watcher = chokidar.watch([context.options.contentDir, context.options.templatesDir], { ignoreInitial: true });
    const watcherReady = new Promise<void>((resolve) => this.watcher?.once('ready', resolve));
    this.watcher.on('all', () => {
      this.rebuild = this.rebuild.then(async () => {
        try {
          await context.build();
        } catch (error) {
          const message = error instanceof Error ? error.message : String(error);
          process.stderr.write(`Rebuild failed: ${message}\n`);
        }
      });
    });
    try {
      await new Promise<void>((resolve, reject) => {
        this.server?.once('error', reject);
        this.server?.listen(this.port, this.host, () => {
          this.server?.off('error', reject);
          resolve();
        });
      });
      await watcherReady;
    } catch (error) {
      await this.closeResources();
      throw error;
    }
    const address = this.server.address();
    if (typeof address === 'object' && address) this.port = address.port;
  }

  async onEnd(): Promise<void> {
    await this.closeResources();
  }

  private async closeResources(): Promise<void> {
    await this.watcher?.close();
    for (const client of this.sockets?.clients ?? []) client.terminate();
    if (!this.server) return;
    await new Promise<void>((resolve, reject) => {
      if (!this.sockets) {
        this.server?.close((error) => error ? reject(error) : resolve());
        return;
      }
      this.sockets.close(() => {
        this.server?.close((error) => error ? reject(error) : resolve());
      });
    });
  }
}

export async function startDevServer(options: ServeOptions = {}): Promise<DevServer> {
  const plugin = new DevServerPlugin(options);
  const engine = await createBuildEngine(options, [plugin]);
  try {
    await engine.build();
  } catch (error) {
    await engine.end();
    throw error;
  }
  return {
    port: plugin.port,
    close: async () => engine.end()
  };
}
