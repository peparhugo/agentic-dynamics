import { createReadStream } from 'node:fs';
import { access } from 'node:fs/promises';
import { createServer, type Server } from 'node:http';
import { extname, join, normalize, resolve } from 'node:path';
import chokidar, { type FSWatcher } from 'chokidar';
import { WebSocket, WebSocketServer } from 'ws';
import { buildSite, type BuildOptions } from './generator.js';

const LIVE_RELOAD_SCRIPT = '<script>(() => { const socket = new WebSocket(`ws://${location.host}/__ssg_live_reload`); socket.onmessage = () => location.reload(); })();</script>';
const MIME_TYPES: Record<string, string> = {
  '.css': 'text/css; charset=utf-8',
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
};

export interface DevServer {
  close(): Promise<void>;
  port: number;
}

function contentType(file: string): string {
  return MIME_TYPES[extname(file).toLowerCase()] ?? 'application/octet-stream';
}

function requestedFile(outputDir: string, requestUrl: string | undefined): string | undefined {
  const pathname = decodeURIComponent(new URL(requestUrl ?? '/', 'http://localhost').pathname);
  const relativePath = pathname === '/' ? 'index.html' : pathname.endsWith('/') ? `${pathname}index.html` : pathname.slice(1);
  const file = resolve(outputDir, normalize(relativePath));
  return file.startsWith(`${resolve(outputDir)}/`) || file === resolve(outputDir) ? file : undefined;
}

export async function startDevServer(options: BuildOptions & { port?: number } = {}): Promise<DevServer> {
  const outputDir = options.outputDir ?? './dist';
  const contentDir = options.contentDir ?? './content';
  const templatesDir = options.templatesDir ?? './templates';
  await buildSite({ contentDir, outputDir, templatesDir });

  const server = createServer(async (request, response) => {
    const file = requestedFile(outputDir, request.url);
    if (!file) {
      response.writeHead(403).end('Forbidden');
      return;
    }
    try {
      await access(file);
      response.writeHead(200, { 'Content-Type': contentType(file) });
      if (extname(file).toLowerCase() === '.html') {
        let html = '';
        for await (const chunk of createReadStream(file, 'utf8')) html += chunk;
        response.end(/<\/body\s*>/i.test(html)
          ? html.replace(/<\/body\s*>/i, `${LIVE_RELOAD_SCRIPT}</body>`)
          : `${html}${LIVE_RELOAD_SCRIPT}`);
      } else createReadStream(file).pipe(response);
    } catch {
      response.writeHead(404).end('Not found');
    }
  });
  const sockets = new WebSocketServer({ noServer: true });
  server.on('upgrade', (request, socket, head) => {
    if (new URL(request.url ?? '/', 'http://localhost').pathname !== '/__ssg_live_reload') return socket.destroy();
    sockets.handleUpgrade(request, socket, head, (client) => sockets.emit('connection', client, request));
  });

  let rebuilding = false;
  let queued = false;
  const rebuild = async (): Promise<void> => {
    if (rebuilding) {
      queued = true;
      return;
    }
    rebuilding = true;
    try {
      await buildSite({ contentDir, outputDir, templatesDir });
      for (const client of sockets.clients) if (client.readyState === WebSocket.OPEN) client.send('reload');
      process.stdout.write('Rebuilt site.\n');
    } catch (error: unknown) {
      process.stderr.write(`Build failed: ${error instanceof Error ? error.message : String(error)}\n`);
    } finally {
      rebuilding = false;
      if (queued) {
        queued = false;
        void rebuild();
      }
    }
  };
  const watcher: FSWatcher = chokidar.watch([contentDir, templatesDir], { ignoreInitial: true });
  watcher.on('all', () => { void rebuild(); });

  await new Promise<void>((resolveListen, reject) => {
    server.once('error', reject);
    server.listen(options.port ?? 3000, 'localhost', () => {
      server.off('error', reject);
      resolveListen();
    });
  });
  const address = server.address();
  if (!address || typeof address === 'string') throw new Error('Unable to determine server port');

  return {
    port: address.port,
    async close(): Promise<void> {
      await watcher.close();
      for (const client of sockets.clients) client.close();
      await new Promise<void>((resolveClose, reject) => server.close((error) => error ? reject(error) : resolveClose()));
      sockets.close();
    },
  };
}
