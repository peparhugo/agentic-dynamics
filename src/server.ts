import { createReadStream, existsSync } from 'node:fs';
import { promises as fs } from 'node:fs';
import { createServer, type Server } from 'node:http';
import path from 'node:path';
import chokidar, { type FSWatcher } from 'chokidar';
import { WebSocketServer } from 'ws';
import { buildSite, type BuildOptions } from './site.js';

export interface ServeOptions extends BuildOptions {
  port?: number;
}

export interface DevelopmentServer {
  port: number;
  close(): Promise<void>;
}

const liveReloadScript = `<script>(function () { const socket = new WebSocket((location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host); socket.addEventListener('message', function (event) { if (event.data === 'reload') location.reload(); }); }());</script>`;

function injectLiveReload(html: string): string {
  const closingBody = /<\/body\s*>/i;
  return closingBody.test(html)
    ? html.replace(closingBody, `${liveReloadScript}</body>`)
    : `${html}${liveReloadScript}`;
}

function contentType(filePath: string): string {
  const extension = path.extname(filePath).toLowerCase();
  if (extension === '.html') return 'text/html; charset=utf-8';
  if (extension === '.css') return 'text/css; charset=utf-8';
  if (extension === '.js') return 'text/javascript; charset=utf-8';
  if (extension === '.json') return 'application/json; charset=utf-8';
  if (extension === '.svg') return 'image/svg+xml';
  return 'application/octet-stream';
}

async function resolveFile(outputDir: string, requestPath: string): Promise<string | undefined> {
  const pathname = decodeURIComponent(requestPath.split('?')[0]);
  const relativePath = pathname === '/' ? 'index.html' : pathname.replace(/^\/+/, '');
  const filePath = path.resolve(outputDir, relativePath);
  if (filePath !== outputDir && !filePath.startsWith(`${outputDir}${path.sep}`)) return undefined;
  try {
    return (await fs.stat(filePath)).isFile() ? filePath : undefined;
  } catch {
    return undefined;
  }
}

export async function startDevelopmentServer(options: ServeOptions = {}): Promise<DevelopmentServer> {
  const contentDir = path.resolve(options.contentDir ?? './content');
  const templatesDir = path.resolve(options.templatesDir ?? './templates');
  const outputDir = path.resolve(options.outputDir ?? './dist');
  const buildOptions = { contentDir, templatesDir, outputDir };
  await buildSite(buildOptions);

  const server = createServer(async (request, response) => {
    const filePath = await resolveFile(outputDir, request.url ?? '/');
    if (!filePath) {
      response.writeHead(404).end('Not found');
      return;
    }
    response.setHeader('Content-Type', contentType(filePath));
    if (path.extname(filePath).toLowerCase() === '.html') {
      response.end(injectLiveReload(await fs.readFile(filePath, 'utf8')));
      return;
    }
    createReadStream(filePath).pipe(response);
  });
  const sockets = new WebSocketServer({ server });
  const watcher: FSWatcher = chokidar.watch([contentDir, templatesDir], { ignoreInitial: true });
  let rebuildTimer: NodeJS.Timeout | undefined;

  watcher.on('all', () => {
    if (rebuildTimer) clearTimeout(rebuildTimer);
    rebuildTimer = setTimeout(() => {
      void buildSite(buildOptions)
        .then(() => sockets.clients.forEach((socket) => socket.send('reload')))
        .catch((error: unknown) => process.stderr.write(`Build failed: ${error instanceof Error ? error.message : String(error)}\n`));
    }, 50);
  });

  await new Promise<void>((resolve, reject) => {
    server.once('error', reject);
    server.listen(options.port ?? 3000, 'localhost', () => {
      server.off('error', reject);
      resolve();
    });
  });
  const address = server.address();
  if (!address || typeof address === 'string') throw new Error('Could not determine development server port');

  return {
    port: address.port,
    async close(): Promise<void> {
      if (rebuildTimer) clearTimeout(rebuildTimer);
      await watcher.close();
      await new Promise<void>((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
    },
  };
}
