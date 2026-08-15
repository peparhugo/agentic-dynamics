import { promises as fs } from 'node:fs';
import { createServer, type Server } from 'node:http';
import path from 'node:path';
import chokidar, { type FSWatcher } from 'chokidar';
import WebSocket, { WebSocketServer } from 'ws';
import { buildSite } from './engine';
import type { BuildContext, BuildOptions, Plugin } from './types';

const LIVE_RELOAD_PATH = '/__ssg_live_reload';
const LIVE_RELOAD_SCRIPT = `<script>
(() => {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const socket = new WebSocket(protocol + '//' + location.host + '${LIVE_RELOAD_PATH}');
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

export interface DevServerOptions extends BuildOptions {
  port?: number;
  host?: string;
  log?: (message: string) => void;
}

export interface DevServer {
  port: number;
  close(): Promise<void>;
}

function injectLiveReload(html: string): string {
  const body = /<\/body\s*>/i;
  return body.test(html) ? html.replace(body, `${LIVE_RELOAD_SCRIPT}\n</body>`) : `${html}\n${LIVE_RELOAD_SCRIPT}\n`;
}

function pathInside(root: string, requestPath: string): string | undefined {
  const resolved = path.resolve(root, `.${requestPath}`);
  const relative = path.relative(root, resolved);
  if (relative === '..' || relative.startsWith(`..${path.sep}`) || path.isAbsolute(relative)) return undefined;
  return resolved;
}

function createStaticServer(outputDir: string): Server {
  return createServer(async (request, response) => {
    if (request.method !== 'GET' && request.method !== 'HEAD') {
      response.writeHead(405, { Allow: 'GET, HEAD' }).end();
      return;
    }

    try {
      const url = new URL(request.url ?? '/', 'http://localhost');
      let requestPath = decodeURIComponent(url.pathname);
      if (requestPath.endsWith('/')) requestPath += 'index.html';
      let filePath = pathInside(outputDir, requestPath);
      if (!filePath) {
        response.writeHead(403).end('Forbidden');
        return;
      }

      let stat = await fs.stat(filePath);
      if (stat.isDirectory()) {
        filePath = path.join(filePath, 'index.html');
        stat = await fs.stat(filePath);
      }
      if (!stat.isFile()) throw Object.assign(new Error('Not found'), { code: 'ENOENT' });

      const extension = path.extname(filePath).toLowerCase();
      const contentType = CONTENT_TYPES[extension] ?? 'application/octet-stream';
      let body: Buffer | string = await fs.readFile(filePath);
      if (extension === '.html') body = injectLiveReload(body.toString('utf8'));
      response.writeHead(200, {
        'Content-Type': contentType,
        'Content-Length': Buffer.byteLength(body),
        'Cache-Control': 'no-store',
      });
      response.end(request.method === 'HEAD' ? undefined : body);
    } catch (error) {
      const code = (error as NodeJS.ErrnoException).code;
      if (code === 'ENOENT' || code === 'ENOTDIR') response.writeHead(404).end('Not found');
      else if (error instanceof URIError) response.writeHead(400).end('Bad request');
      else response.writeHead(500).end('Internal server error');
    }
  });
}

async function createDevServer(options: DevServerOptions = {}): Promise<DevServer> {
  const port = options.port ?? 3000;
  const host = options.host ?? 'localhost';
  const outputDir = path.resolve(options.outputDir ?? './dist');
  const contentDir = path.resolve(options.contentDir ?? './content');
  const templatesDir = path.resolve(options.templatesDir ?? './templates');
  const log = options.log ?? ((message: string) => process.stdout.write(`${message}\n`));
  const buildOptions: BuildOptions = {
    contentDir,
    outputDir,
    templatesDir,
    configFile: options.configFile,
    plugins: options.plugins,
  };

  await buildSite(buildOptions);

  const server = createStaticServer(outputDir);
  const sockets = new WebSocketServer({ noServer: true });
  server.on('upgrade', (request, socket, head) => {
    const pathname = new URL(request.url ?? '/', 'http://localhost').pathname;
    if (pathname !== LIVE_RELOAD_PATH) {
      socket.destroy();
      return;
    }
    sockets.handleUpgrade(request, socket, head, (client) => sockets.emit('connection', client, request));
  });

  let rebuilding = false;
  let rebuildPending = false;
  const rebuild = async (): Promise<void> => {
    if (rebuilding) {
      rebuildPending = true;
      return;
    }
    rebuilding = true;
    do {
      rebuildPending = false;
      try {
        const pages = await buildSite(buildOptions);
        log(`Rebuilt ${pages.length} page${pages.length === 1 ? '' : 's'}.`);
        for (const client of sockets.clients) {
          if (client.readyState === WebSocket.OPEN) client.send('reload');
        }
      } catch (error) {
        log(`Build failed: ${error instanceof Error ? error.message : String(error)}`);
      }
    } while (rebuildPending);
    rebuilding = false;
  };

  const configFile = path.resolve(options.configFile ?? './ssg.config.ts');
  const watcher: FSWatcher = chokidar.watch([
    contentDir,
    templatesDir,
    configFile,
    path.join(path.dirname(configFile), 'plugins'),
  ], {
    ignoreInitial: true,
    awaitWriteFinish: { stabilityThreshold: 100, pollInterval: 20 },
  });
  const watcherReady = new Promise<void>((resolve) => watcher.once('ready', resolve));
  watcher.on('all', () => void rebuild());

  try {
    await new Promise<void>((resolve, reject) => {
      server.once('error', reject);
      server.listen(port, host, () => {
        server.off('error', reject);
        resolve();
      });
    });
    await watcherReady;
  } catch (error) {
    await watcher.close();
    sockets.close();
    throw error;
  }

  const address = server.address();
  const actualPort = typeof address === 'object' && address ? address.port : port;
  log(`Serving ${outputDir} at http://${host}:${actualPort}`);

  return {
    port: actualPort,
    async close(): Promise<void> {
      await watcher.close();
      for (const client of sockets.clients) client.terminate();
      await Promise.all([
        new Promise<void>((resolve) => sockets.close(() => resolve())),
        new Promise<void>((resolve, reject) => server.close((error) => error ? reject(error) : resolve())),
      ]);
    },
  };
}

export class DevServerPlugin implements Plugin, DevServer {
  readonly name = 'dev-server';
  port: number;
  private server?: DevServer;

  constructor(private readonly options: DevServerOptions = {}) {
    this.port = options.port ?? 3000;
  }

  async onStart(_context?: BuildContext): Promise<void> {
    if (this.server) return;
    this.server = await createDevServer(this.options);
    this.port = this.server.port;
  }

  async onEnd(_context?: BuildContext): Promise<void> {
    await this.close();
  }

  async close(): Promise<void> {
    const server = this.server;
    this.server = undefined;
    await server?.close();
  }
}

export async function startDevServer(options: DevServerOptions = {}): Promise<DevServer> {
  const plugin = new DevServerPlugin(options);
  await plugin.onStart();
  return plugin;
}
