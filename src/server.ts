import { promises as fs } from 'node:fs';
import http, { IncomingMessage, ServerResponse } from 'node:http';
import path from 'node:path';
import { buildSite, BuildOptions } from './index';

const chokidar = require('chokidar') as {
  watch(paths: string[], options: { ignoreInitial: boolean }): {
    on(event: 'all', listener: () => void): void;
    once(event: 'ready', listener: () => void): void;
    close(): Promise<void>;
  };
};

interface WebSocketClient {
  readyState: number;
  send(message: string): void;
  terminate(): void;
}

interface WebSocketServerLike {
  clients: Set<WebSocketClient>;
  close(callback: (error?: Error) => void): void;
}

const { WebSocketServer } = require('ws') as {
  WebSocketServer: new (options: { server: http.Server }) => WebSocketServerLike;
};

export interface ServeOptions extends BuildOptions {
  port?: number;
}

export interface DevServer {
  port: number;
  close(): Promise<void>;
}

const LIVE_RELOAD_SCRIPT = `<script>
(() => {
  const socket = new WebSocket((location.protocol === 'https:' ? 'wss' : 'ws') + '://' + location.host);
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
  const bodyEnd = html.toLowerCase().lastIndexOf('</body>');
  if (bodyEnd === -1) return `${html}\n${LIVE_RELOAD_SCRIPT}\n`;
  return `${html.slice(0, bodyEnd)}${LIVE_RELOAD_SCRIPT}\n${html.slice(bodyEnd)}`;
}

async function serveFile(outputDir: string, request: IncomingMessage, response: ServerResponse): Promise<void> {
  let pathname: string;
  try {
    pathname = decodeURIComponent(new URL(request.url ?? '/', 'http://localhost').pathname);
  } catch {
    response.writeHead(400).end('Bad request');
    return;
  }

  const relativePath = pathname.endsWith('/') ? `${pathname}index.html` : pathname;
  const filePath = path.resolve(outputDir, `.${relativePath}`);
  if (filePath !== outputDir && !filePath.startsWith(`${outputDir}${path.sep}`)) {
    response.writeHead(403).end('Forbidden');
    return;
  }

  try {
    let contents = await fs.readFile(filePath);
    const extension = path.extname(filePath).toLowerCase();
    if (extension === '.html') contents = Buffer.from(injectLiveReload(contents.toString('utf8')));
    response.writeHead(200, { 'Content-Type': CONTENT_TYPES[extension] ?? 'application/octet-stream' });
    response.end(contents);
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT' || (error as NodeJS.ErrnoException).code === 'EISDIR') {
      response.writeHead(404).end('Not found');
      return;
    }
    response.writeHead(500).end('Internal server error');
  }
}

export async function startDevServer(options: ServeOptions = {}): Promise<DevServer> {
  const outputDir = path.resolve(options.outputDir ?? './dist');
  const contentDir = path.resolve(options.contentDir ?? './content');
  const templatesDir = path.resolve(options.templatesDir ?? './templates');
  const port = options.port ?? 3000;
  const buildOptions = { contentDir, outputDir, templatesDir };

  await buildSite(buildOptions);

  const server = http.createServer((request, response) => {
    void serveFile(outputDir, request, response);
  });
  const sockets = new WebSocketServer({ server });
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
        await buildSite(buildOptions);
        for (const client of sockets.clients) {
          if (client.readyState === 1) client.send('reload');
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        process.stderr.write(`Rebuild failed: ${message}\n`);
      }
    } while (rebuildPending);
    rebuilding = false;
  };

  const watcher = chokidar.watch([contentDir, templatesDir], { ignoreInitial: true });
  watcher.on('all', () => void rebuild());
  await new Promise<void>((resolve) => watcher.once('ready', resolve));

  try {
    await new Promise<void>((resolve, reject) => {
      const onError = (error: Error): void => reject(error);
      server.once('error', onError);
      server.listen(port, 'localhost', () => {
        server.off('error', onError);
        resolve();
      });
    });
  } catch (error) {
    await watcher.close();
    throw error;
  }

  const address = server.address();
  const listeningPort = typeof address === 'object' && address ? address.port : port;
  return {
    port: listeningPort,
    async close(): Promise<void> {
      await watcher.close();
      for (const client of sockets.clients) client.terminate();
      await new Promise<void>((resolve, reject) => {
        sockets.close((error) => error ? reject(error) : resolve());
      });
      await new Promise<void>((resolve, reject) => {
        server.close((error) => error ? reject(error) : resolve());
      });
    },
  };
}
