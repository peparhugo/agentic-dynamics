import { createReadStream } from 'node:fs';
import { access } from 'node:fs/promises';
import { createServer, Server } from 'node:http';
import { extname, join, resolve, sep } from 'node:path';
import chokidar, { FSWatcher } from 'chokidar';
import { WebSocketServer } from 'ws';
import { buildSite } from './build';

const reloadScript = `<script>(() => { const socket = new WebSocket((location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host); socket.onmessage = () => location.reload(); })();</script>`;

const contentTypes: Record<string, string> = {
  '.css': 'text/css; charset=utf-8',
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
};

export interface DevServer {
  port: number;
  close(): Promise<void>;
}

export interface ServeOptions {
  contentDirectory?: string;
  outputDirectory?: string;
  templatesDirectory?: string;
  port?: number;
}

function injectReloadScript(page: string): string {
  return page.replace(/<\/body\s*>/i, `${reloadScript}</body>`);
}

function isInside(root: string, path: string): boolean {
  return path === root || path.startsWith(`${root}${sep}`);
}

export async function startDevServer(options: ServeOptions = {}): Promise<DevServer> {
  const contentDirectory = options.contentDirectory ?? './content';
  const outputDirectory = options.outputDirectory ?? './dist';
  const templatesDirectory = options.templatesDirectory ?? './templates';
  const outputRoot = resolve(outputDirectory);
  await buildSite(contentDirectory, outputDirectory, templatesDirectory);

  const server = createServer(async (request, response) => {
    try {
      const pathname = decodeURIComponent(new URL(request.url ?? '/', 'http://localhost').pathname);
      const filename = pathname === '/' ? 'index.html' : pathname.slice(1);
      const file = resolve(outputRoot, filename);
      if (!isInside(outputRoot, file)) {
        response.writeHead(403).end();
        return;
      }
      await access(file);
      const contentType = contentTypes[extname(file).toLowerCase()] ?? 'application/octet-stream';
      if (extname(file).toLowerCase() === '.html') {
        const chunks: Buffer[] = [];
        createReadStream(file).on('data', (chunk: Buffer) => chunks.push(chunk)).on('error', () => response.writeHead(500).end()).on('end', () => {
          response.writeHead(200, { 'Content-Type': contentType });
          response.end(injectReloadScript(Buffer.concat(chunks).toString('utf8')));
        });
        return;
      }
      response.writeHead(200, { 'Content-Type': contentType });
      createReadStream(file).pipe(response);
    } catch {
      response.writeHead(404).end();
    }
  });
  const sockets = new WebSocketServer({ server });
  let rebuilding = false;
  let rebuildQueued = false;
  const rebuild = async (): Promise<void> => {
    if (rebuilding) {
      rebuildQueued = true;
      return;
    }
    rebuilding = true;
    try {
      await buildSite(contentDirectory, outputDirectory, templatesDirectory);
      for (const socket of sockets.clients) socket.send('reload');
      process.stdout.write('Rebuilt site.\n');
    } catch (error: unknown) {
      process.stderr.write(`Build failed: ${error instanceof Error ? error.message : String(error)}\n`);
    } finally {
      rebuilding = false;
      if (rebuildQueued) {
        rebuildQueued = false;
        void rebuild();
      }
    }
  };
  const watcher: FSWatcher = chokidar.watch([contentDirectory, templatesDirectory], { ignoreInitial: true });
  watcher.on('all', () => { void rebuild(); });

  await new Promise<void>((resolveListen, reject) => {
    server.once('error', reject);
    server.listen(options.port ?? 3000, 'localhost', () => {
      server.off('error', reject);
      resolveListen();
    });
  });
  const address = server.address();
  if (!address || typeof address === 'string') throw new Error('Unable to determine dev server port');
  return {
    port: address.port,
    async close(): Promise<void> {
      await watcher.close();
      sockets.close();
      await new Promise<void>((resolveClose, reject) => server.close((error) => error ? reject(error) : resolveClose()));
    },
  };
}
