import { promises as fs } from 'node:fs';
import http, { IncomingMessage, ServerResponse } from 'node:http';
import path from 'node:path';
import chokidar, { FSWatcher } from 'chokidar';
import { WebSocket, WebSocketServer } from 'ws';
import { buildSite, BuildOptions } from './generator';

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
  '.css': 'text/css; charset=utf-8',
  '.gif': 'image/gif',
  '.html': 'text/html; charset=utf-8',
  '.ico': 'image/x-icon',
  '.jpeg': 'image/jpeg',
  '.jpg': 'image/jpeg',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.svg': 'image/svg+xml; charset=utf-8',
  '.webp': 'image/webp'
};

function injectLiveReload(html: string): string {
  const closingBody = /<\/body\s*>/i;
  return closingBody.test(html)
    ? html.replace(closingBody, `${liveReloadScript}\n</body>`)
    : `${html}\n${liveReloadScript}`;
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

export async function serveSite(options: ServeOptions = {}): Promise<DevServer> {
  const port = options.port ?? 3000;
  const outputDir = path.resolve(options.outputDir ?? './dist');
  const contentDir = path.resolve(options.contentDir ?? './content');
  const templatesDir = path.resolve(options.templatesDir ?? './templates');
  const buildOptions: BuildOptions = { ...options };
  delete (buildOptions as ServeOptions).port;

  await buildSite(buildOptions);

  const server = http.createServer((request, response) => {
    void serveFile(request, response, outputDir).catch((error: unknown) => {
      const message = error instanceof Error ? error.message : String(error);
      response.writeHead(500, { 'Content-Type': 'text/plain; charset=utf-8' });
      response.end(`Server error: ${message}`);
    });
  });
  const sockets = new WebSocketServer({ server, path: '/__ssg_live_reload' });
  let watcher: FSWatcher | undefined;

  try {
    await new Promise<void>((resolve, reject) => {
      server.once('error', reject);
      server.listen(port, 'localhost', () => {
        server.off('error', reject);
        resolve();
      });
    });

    let rebuildPending = false;
    let rebuilding = false;
    const rebuild = async (): Promise<void> => {
      rebuildPending = true;
      if (rebuilding) return;
      rebuilding = true;
      while (rebuildPending) {
        rebuildPending = false;
        try {
          const pages = await buildSite(buildOptions);
          process.stdout.write(`Rebuilt ${pages.length} page${pages.length === 1 ? '' : 's'}.\n`);
          for (const client of sockets.clients) {
            if (client.readyState === WebSocket.OPEN) client.send('reload');
          }
        } catch (error) {
          const message = error instanceof Error ? error.message : String(error);
          process.stderr.write(`Rebuild failed: ${message}\n`);
        }
      }
      rebuilding = false;
    };

    watcher = chokidar.watch([contentDir, templatesDir], { ignoreInitial: true });
    watcher.on('all', () => void rebuild());
    await new Promise<void>((resolve, reject) => {
      watcher?.once('ready', resolve);
      watcher?.once('error', reject);
    });

    const address = server.address();
    const listeningPort = typeof address === 'object' && address ? address.port : port;
    process.stdout.write(`Serving ${outputDir} at http://localhost:${listeningPort}\n`);
    return {
      port: listeningPort,
      async close(): Promise<void> {
        await watcher?.close();
        for (const client of sockets.clients) client.terminate();
        await new Promise<void>((resolve, reject) => sockets.close((error) => error ? reject(error) : resolve()));
        await new Promise<void>((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
      }
    };
  } catch (error) {
    await watcher?.close();
    sockets.close();
    server.close();
    throw error;
  }
}
