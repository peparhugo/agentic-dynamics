import { createReadStream } from 'node:fs';
import { readFile, stat } from 'node:fs/promises';
import { createServer, IncomingMessage, ServerResponse } from 'node:http';
import { extname, resolve, sep } from 'node:path';
import chokidar from 'chokidar';
import { WebSocketServer } from 'ws';
import { BuildOptions, buildSite } from './generator';

export interface ServeOptions extends BuildOptions {
  port?: number;
}

export interface DevServer {
  port: number;
  close(): Promise<void>;
}

const liveReloadScript = `<script>(() => { const socket = new WebSocket(\`ws://\${location.host}\`); socket.addEventListener('message', () => location.reload()); })();</script>`;

const contentTypes: Record<string, string> = {
  '.css': 'text/css; charset=utf-8',
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.txt': 'text/plain; charset=utf-8'
};

function injectLiveReload(document: string): string {
  return /<\/body\s*>/i.test(document)
    ? document.replace(/<\/body\s*>/i, `${liveReloadScript}</body>`)
    : `${document}${liveReloadScript}`;
}

function filePathFor(request: IncomingMessage, outputDir: string): string | undefined {
  const pathname = new URL(request.url ?? '/', 'http://localhost').pathname;
  const decodedPath = decodeURIComponent(pathname);
  const relativePath = decodedPath === '/' ? 'index.html' : decodedPath.replace(/^\/+/, '');
  const filePath = resolve(outputDir, relativePath);
  return filePath === outputDir || filePath.startsWith(`${outputDir}${sep}`) ? filePath : undefined;
}

async function serveFile(request: IncomingMessage, response: ServerResponse, outputDir: string): Promise<void> {
  let filePath: string | undefined;
  try {
    filePath = filePathFor(request, outputDir);
  } catch {
    response.writeHead(400).end('Bad request');
    return;
  }
  if (!filePath) {
    response.writeHead(403).end('Forbidden');
    return;
  }

  try {
    const details = await stat(filePath);
    if (!details.isFile()) throw new Error('Not a file');
    const extension = extname(filePath).toLowerCase();
    response.setHeader('Content-Type', contentTypes[extension] ?? 'application/octet-stream');
    if (extension === '.html') {
      response.end(injectLiveReload(await readFile(filePath, 'utf8')));
      return;
    }
    createReadStream(filePath).on('error', () => response.writeHead(500).end('Internal server error')).pipe(response);
  } catch {
    response.writeHead(404).end('Not found');
  }
}

export async function startDevServer(options: ServeOptions = {}): Promise<DevServer> {
  const outputDir = resolve(options.outputDir ?? 'dist');
  const contentDir = resolve(options.contentDir ?? 'content');
  const templatesDir = resolve(options.templatesDir ?? 'templates');
  const server = createServer((request, response) => void serveFile(request, response, outputDir));
  const sockets = new WebSocketServer({ server });
  let rebuilding = false;
  let rebuildQueued = false;

  const rebuild = async (): Promise<void> => {
    if (rebuilding) return;
    rebuilding = true;
    try {
      const pages = await buildSite({ contentDir, outputDir, templatesDir });
      console.log(`Generated ${pages.length} page(s).`);
      for (const socket of sockets.clients) socket.send('reload');
    } catch (error: unknown) {
      console.error(error instanceof Error ? error.message : String(error));
    } finally {
      rebuilding = false;
      if (rebuildQueued) {
        rebuildQueued = false;
        void rebuild();
      }
    }
  };

  const watcher = chokidar.watch([contentDir, templatesDir], { ignoreInitial: true });
  watcher.on('all', () => {
    if (rebuilding) rebuildQueued = true;
    else void rebuild();
  });
  await Promise.all([
    rebuild(),
    new Promise<void>((complete) => watcher.once('ready', complete))
  ]);
  await new Promise<void>((complete) => server.listen(options.port ?? 3000, 'localhost', complete));
  const address = server.address();
  if (!address || typeof address === 'string') throw new Error('Could not determine server port');
  console.log(`Serving ${outputDir} at http://localhost:${address.port}`);

  return {
    port: address.port,
    async close(): Promise<void> {
      await watcher.close();
      for (const socket of sockets.clients) socket.terminate();
      await new Promise<void>((complete, reject) => sockets.close((error) => error ? reject(error) : complete()));
      await new Promise<void>((complete, reject) => server.close((error) => error ? reject(error) : complete()));
    }
  };
}
