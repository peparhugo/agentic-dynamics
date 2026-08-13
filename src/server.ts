import { createReadStream, promises as fs } from 'node:fs';
import { createServer, type Server } from 'node:http';
import path from 'node:path';
import chokidar, { type FSWatcher } from 'chokidar';
import { WebSocket, WebSocketServer } from 'ws';
import { buildSite, type BuildOptions } from './index';

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

export async function serveSite(options: ServeOptions = {}): Promise<DevServer> {
  const outputDir = path.resolve(options.outputDir ?? './dist');
  const contentDir = path.resolve(options.contentDir ?? './content');
  const templatesDir = path.resolve(options.templatesDir ?? './templates');
  const buildOptions = { contentDir, outputDir, templatesDir };
  await buildSite(buildOptions);

  const server = createServer(async (request, response) => {
    if (request.method !== 'GET' && request.method !== 'HEAD') {
      response.writeHead(405, { Allow: 'GET, HEAD' }).end();
      return;
    }

    const file = await requestedFile(outputDir, request.url ?? '/');
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
  const sockets = new WebSocketServer({ server });
  const watcher: FSWatcher = chokidar.watch([contentDir, templatesDir], { ignoreInitial: true });
  const watcherReady = new Promise<void>((resolve) => watcher.once('ready', resolve));
  let building = false;
  let rebuildPending = false;

  const rebuild = async (): Promise<void> => {
    if (building) {
      rebuildPending = true;
      return;
    }
    building = true;
    do {
      rebuildPending = false;
      try {
        const pages = await buildSite(buildOptions);
        console.log(`Rebuilt ${pages.length} page${pages.length === 1 ? '' : 's'}.`);
        for (const client of sockets.clients) {
          if (client.readyState === WebSocket.OPEN) client.send('reload');
        }
      } catch (error) {
        console.error(`Rebuild failed: ${error instanceof Error ? error.message : String(error)}`);
      }
    } while (rebuildPending);
    building = false;
  };
  watcher.on('all', () => void rebuild());

  try {
    await watcherReady;
    const port = await listen(server, options.port ?? 3000);
    return {
      port,
      async close(): Promise<void> {
        await watcher.close();
        for (const client of sockets.clients) client.terminate();
        await new Promise<void>((resolve, reject) => {
          sockets.close(() => server.close((error) => error ? reject(error) : resolve()));
        });
      },
    };
  } catch (error) {
    await watcher.close();
    sockets.close();
    throw error;
  }
}
