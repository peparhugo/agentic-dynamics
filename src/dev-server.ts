import { createReadStream, existsSync } from 'node:fs';
import { stat } from 'node:fs/promises';
import { createServer } from 'node:http';
import { extname, join, normalize, resolve, sep } from 'node:path';
import chokidar, { FSWatcher } from 'chokidar';
import { WebSocketServer } from 'ws';
import { BuildOptions, buildSite } from './generator';

export interface ServeOptions extends BuildOptions {
  port?: number;
}

export interface DevelopmentServer {
  port: number;
  close(): Promise<void>;
}

const reloadClient = `<script>(() => {
  const socket = new WebSocket((location.protocol === 'https:' ? 'wss' : 'ws') + '://' + location.host);
  socket.addEventListener('message', event => { if (event.data === 'reload') location.reload(); });
})();</script>`;

const contentTypes: Record<string, string> = {
  '.css': 'text/css; charset=utf-8',
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
};

function servedPath(outputDir: string, requestUrl: string): string | undefined {
  const pathname = decodeURIComponent(new URL(requestUrl, 'http://localhost').pathname);
  const requested = pathname === '/' ? 'index.html' : pathname.replace(/^\/+/, '');
  const outputRoot = resolve(outputDir);
  const file = resolve(outputRoot, requested);
  return file === outputRoot || file.startsWith(`${outputRoot}${sep}`) ? file : undefined;
}

async function sendFile(outputDir: string, requestUrl: string, response: import('node:http').ServerResponse): Promise<void> {
  const file = servedPath(outputDir, requestUrl);
  if (file === undefined || !existsSync(file) || (await stat(file)).isDirectory()) {
    response.writeHead(404).end('Not found');
    return;
  }

  if (extname(file) === '.html') {
    const html = await import('node:fs/promises').then(({ readFile }) => readFile(file, 'utf8'));
    const withReloadClient = /<\/body\s*>/i.test(html)
      ? html.replace(/<\/body\s*>/i, `${reloadClient}</body>`)
      : `${html}${reloadClient}`;
    response.writeHead(200, { 'Content-Type': contentTypes['.html'] }).end(withReloadClient);
    return;
  }

  response.writeHead(200, { 'Content-Type': contentTypes[extname(file)] ?? 'application/octet-stream' });
  createReadStream(file).pipe(response);
}

export async function startDevelopmentServer(options: ServeOptions = {}): Promise<DevelopmentServer> {
  const contentDir = options.contentDir ?? './content';
  const templateDir = options.templateDir ?? './templates';
  const outputDir = options.outputDir ?? './dist';
  const port = options.port ?? 3000;
  const buildOptions = { contentDir, templateDir, outputDir };

  await buildSite(buildOptions);
  const server = createServer((request, response) => {
    void sendFile(outputDir, request.url ?? '/', response).catch(() => response.writeHead(500).end('Server error'));
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
      await buildSite(buildOptions);
      for (const client of sockets.clients) client.send('reload');
      console.log('Rebuilt site.');
    } catch (error) {
      console.error(error instanceof Error ? error.message : error);
    } finally {
      rebuilding = false;
      if (rebuildQueued) {
        rebuildQueued = false;
        void rebuild();
      }
    }
  };

  const watcher: FSWatcher = chokidar.watch([contentDir, templateDir], { ignoreInitial: true });
  watcher.on('all', () => void rebuild());
  await new Promise<void>((resolveListen) => server.listen(port, 'localhost', resolveListen));
  const address = server.address();
  const listeningPort = typeof address === 'object' && address !== null ? address.port : port;
  console.log(`Serving site at http://localhost:${listeningPort}`);

  return {
    port: listeningPort,
    close: async () => {
      await watcher.close();
      for (const client of sockets.clients) client.terminate();
      sockets.close();
      await new Promise<void>((resolveClose, rejectClose) => server.close((error) => error ? rejectClose(error) : resolveClose()));
    },
  };
}
