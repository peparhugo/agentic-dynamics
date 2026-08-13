import { createReadStream } from 'node:fs';
import { access, readFile } from 'node:fs/promises';
import { createServer, type Server } from 'node:http';
import { extname, join, normalize, resolve, sep } from 'node:path';
import { watch, type FSWatcher } from 'chokidar';
import { WebSocketServer } from 'ws';
import { buildSite } from '../generator.js';
import type { BuildOptions, Plugin } from '../plugin.js';

export interface ServeOptions extends BuildOptions {
  port?: number;
}

export interface DevelopmentServer {
  port: number;
  close(): Promise<void>;
}

const liveReloadScript = `<script>new WebSocket((location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/__ssg_live_reload').addEventListener('message', function (event) { if (event.data === 'reload') location.reload(); });</script>`;
const contentTypes: Record<string, string> = { '.css': 'text/css; charset=utf-8', '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.json': 'application/json; charset=utf-8', '.svg': 'image/svg+xml' };

function requestedFile(outputDirectory: string, requestUrl: string): string | undefined {
  const pathname = decodeURIComponent(new URL(requestUrl, 'http://localhost').pathname);
  const filePath = resolve(outputDirectory, normalize(pathname === '/' ? 'index.html' : pathname.replace(/^[/\\]+/, '')));
  return filePath === outputDirectory || filePath.startsWith(`${outputDirectory}${sep}`) ? filePath : undefined;
}

async function fileExists(filePath: string): Promise<boolean> {
  try { await access(filePath); return true; } catch { return false; }
}

function closeServer(server: Server): Promise<void> {
  return new Promise((resolveClose, reject) => server.close((error) => error ? reject(error) : resolveClose()));
}

export class DevServerPlugin implements Plugin {
  async serve(options: ServeOptions = {}): Promise<DevelopmentServer> {
    const outputDirectory = resolve(options.output ?? 'dist');
    const contentDirectory = resolve(options.content ?? 'content');
    const templatesDirectory = resolve(options.templates ?? 'templates');
    await buildSite(options);
    const server = createServer(async (request, response) => {
      try {
        const filePath = requestedFile(outputDirectory, request.url ?? '/');
        if (!filePath || !(await fileExists(filePath))) {
          response.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
          response.end('Not found');
          return;
        }
        const contentType = contentTypes[extname(filePath).toLowerCase()] ?? 'application/octet-stream';
        response.writeHead(200, { 'Content-Type': contentType });
        if (extname(filePath).toLowerCase() === '.html') {
          const html = await readFile(filePath, 'utf8');
          response.end(html.includes('</body>') ? html.replace('</body>', `${liveReloadScript}</body>`) : `${html}${liveReloadScript}`);
        } else createReadStream(filePath).pipe(response);
      } catch {
        response.writeHead(500, { 'Content-Type': 'text/plain; charset=utf-8' });
        response.end('Internal server error');
      }
    });
    const webSockets = new WebSocketServer({ noServer: true });
    server.on('upgrade', (request, socket, head) => {
      if (new URL(request.url ?? '/', 'http://localhost').pathname !== '/__ssg_live_reload') return socket.destroy();
      webSockets.handleUpgrade(request, socket, head, (webSocket) => webSockets.emit('connection', webSocket, request));
    });
    let rebuilding = false;
    let rebuildQueued = false;
    const rebuild = async (): Promise<void> => {
      if (rebuilding) { rebuildQueued = true; return; }
      rebuilding = true;
      try {
        await buildSite(options);
        for (const client of webSockets.clients) client.send('reload');
        process.stdout.write('Rebuilt site.\n');
      } catch (error) {
        process.stderr.write(`Build failed: ${error instanceof Error ? error.message : String(error)}\n`);
      } finally {
        rebuilding = false;
        if (rebuildQueued) { rebuildQueued = false; void rebuild(); }
      }
    };
    const watcher = watch([contentDirectory, templatesDirectory], { ignoreInitial: true });
    watcher.on('all', () => void rebuild());
    await new Promise<void>((resolveListen, reject) => {
      server.once('error', reject);
      server.listen(options.port ?? 3000, 'localhost', () => { server.off('error', reject); resolveListen(); });
    });
    const address = server.address();
    if (!address || typeof address === 'string') throw new Error('Unable to determine development server port');
    process.stdout.write(`Serving on http://localhost:${address.port}\n`);
    return {
      port: address.port,
      async close(): Promise<void> {
        await (watcher as FSWatcher).close();
        for (const client of webSockets.clients) client.close();
        await new Promise<void>((resolveClose) => webSockets.close(() => resolveClose()));
        await closeServer(server);
      },
    };
  }
}
