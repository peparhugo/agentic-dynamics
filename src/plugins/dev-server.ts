import { promises as fs } from 'node:fs';
import http, { type ServerResponse } from 'node:http';
import path from 'node:path';
import chokidar, { type FSWatcher } from 'chokidar';
import type { BuildOptions } from '../index';
import type { Plugin } from '../plugin';

interface WebSocketClient {
  readyState: number;
  send(data: string): void;
}

interface WebSocketServerInstance {
  clients: Set<WebSocketClient>;
  close(callback: (error?: Error) => void): void;
}

interface WebSocketServerConstructor {
  new(options: { server: http.Server }): WebSocketServerInstance;
}

const { WebSocketServer } = require('ws') as { WebSocketServer: WebSocketServerConstructor };

export interface ServeOptions extends BuildOptions {
  port?: number;
}

export interface DevServer {
  port: number;
  close(): Promise<void>;
}

const liveReloadScript = `<script>
(() => {
  const socket = new WebSocket((location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host);
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
  '.webp': 'image/webp',
};

function injectLiveReload(html: string): string {
  return /<\/body\s*>/i.test(html)
    ? html.replace(/<\/body\s*>/i, `${liveReloadScript}\n</body>`)
    : `${html}\n${liveReloadScript}\n`;
}

function send(response: ServerResponse, status: number, body: string): void {
  response.writeHead(status, { 'Content-Type': 'text/plain; charset=utf-8' });
  response.end(body);
}

async function serveFile(outputDir: string, request: http.IncomingMessage, response: ServerResponse): Promise<void> {
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
  const relativePath = pathname.endsWith('/') ? `${pathname}index.html` : pathname;
  const filePath = path.resolve(outputDir, `.${relativePath}`);
  const relative = path.relative(outputDir, filePath);
  if (relative.startsWith(`..${path.sep}`) || relative === '..' || path.isAbsolute(relative)) {
    send(response, 403, 'Forbidden');
    return;
  }
  try {
    const stat = await fs.stat(filePath);
    if (!stat.isFile()) {
      send(response, 404, 'Not Found');
      return;
    }
    const isHtml = path.extname(filePath).toLowerCase() === '.html';
    const file = await fs.readFile(filePath);
    const body = isHtml ? Buffer.from(injectLiveReload(file.toString('utf8'))) : file;
    response.writeHead(200, {
      'Content-Length': body.byteLength,
      'Content-Type': contentTypes[path.extname(filePath).toLowerCase()] ?? 'application/octet-stream',
    });
    response.end(request.method === 'HEAD' ? undefined : body);
  } catch (error: unknown) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') {
      send(response, 404, 'Not Found');
      return;
    }
    throw error;
  }
}

export class DevServerPlugin implements Plugin {
  readonly name = 'dev-server';

  async start(options: ServeOptions = {}): Promise<DevServer> {
    const { buildSite } = require('../index') as typeof import('../index');
    const contentDir = path.resolve(options.contentDir ?? './content');
    const outputDir = path.resolve(options.outputDir ?? './dist');
    const templatesDir = path.resolve(options.templatesDir ?? './templates');
    const port = options.port ?? 3000;
    const buildOptions: BuildOptions = { ...options, contentDir, outputDir, templatesDir };
    delete (buildOptions as ServeOptions).port;
    await buildSite(buildOptions);

    const server = http.createServer((request, response) => {
      void serveFile(outputDir, request, response).catch((error: unknown) => {
        process.stderr.write(`Server error: ${error instanceof Error ? error.message : String(error)}\n`);
        if (!response.headersSent) send(response, 500, 'Internal Server Error');
        else response.end();
      });
    });
    const sockets = new WebSocketServer({ server });
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
        rebuildQueued = true;
        if (rebuilding) return;
        rebuilding = true;
        while (rebuildQueued) {
          rebuildQueued = false;
          try {
            await buildSite(buildOptions);
            for (const client of sockets.clients) if (client.readyState === 1) client.send('reload');
            process.stdout.write('Rebuilt site.\n');
          } catch (error: unknown) {
            process.stderr.write(`Rebuild failed: ${error instanceof Error ? error.message : String(error)}\n`);
          }
        }
        rebuilding = false;
      };
      watcher = chokidar.watch([contentDir, templatesDir], { ignoreInitial: true });
      watcher.on('all', () => void rebuild());
      watcher.on('error', (error) => {
        process.stderr.write(`Watcher error: ${error instanceof Error ? error.message : String(error)}\n`);
      });
      await new Promise<void>((resolve, reject) => {
        watcher?.once('ready', resolve);
        watcher?.once('error', reject);
      });

      const address = server.address();
      const listeningPort = typeof address === 'object' && address ? address.port : port;
      return {
        port: listeningPort,
        async close() {
          await watcher?.close();
          await Promise.all([
            new Promise<void>((resolve, reject) => sockets.close((error) => error ? reject(error) : resolve())),
            new Promise<void>((resolve, reject) => server.close((error) => error ? reject(error) : resolve())),
          ]);
        },
      };
    } catch (error) {
      await watcher?.close();
      server.close();
      throw error;
    }
  }
}
