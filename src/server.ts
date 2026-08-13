import chokidar, { FSWatcher } from 'chokidar';
import { createReadStream, promises as fs } from 'node:fs';
import { createServer, Server } from 'node:http';
import path from 'node:path';
import { WebSocket, WebSocketServer } from 'ws';
import { buildSite, BuildOptions } from './index';

const reloadScript = `<script>
(() => {
  const connect = () => {
    const socket = new WebSocket((location.protocol === 'https:' ? 'wss' : 'ws') + '://' + location.host + '/__ssg_reload');
    socket.addEventListener('message', event => event.data === 'reload' && location.reload());
    socket.addEventListener('close', () => setTimeout(connect, 500));
  };
  connect();
})();
</script>`;

const contentTypes: Record<string, string> = {
  '.css': 'text/css; charset=utf-8',
  '.html': 'text/html; charset=utf-8',
  '.ico': 'image/x-icon',
  '.jpeg': 'image/jpeg',
  '.jpg': 'image/jpeg',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.svg': 'image/svg+xml',
  '.webp': 'image/webp'
};

export interface DevServerOptions extends BuildOptions {
  port?: number;
  host?: string;
  io?: { stderr: { write(chunk: string): unknown } };
}

export interface DevServer {
  port: number;
  close(): Promise<void>;
}

function injectReload(html: string): string {
  const closingBody = /<\/body\s*>/i;
  return closingBody.test(html)
    ? html.replace(closingBody, `${reloadScript}\n</body>`)
    : `${html}\n${reloadScript}\n`;
}

function listen(server: Server, port: number, host: string): Promise<void> {
  return new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(port, host, () => {
      server.off('error', reject);
      resolve();
    });
  });
}

export async function startDevServer(options: DevServerOptions = {}): Promise<DevServer> {
  const outputDir = path.resolve(options.outputDir ?? 'dist');
  const contentDir = path.resolve(options.contentDir ?? 'content');
  const templatesDir = path.resolve(options.templatesDir ?? 'templates');
  const port = options.port ?? 3000;
  const host = options.host ?? 'localhost';

  await buildSite({ contentDir, outputDir, templatesDir });

  const server = createServer(async (request, response) => {
    try {
      const pathname = decodeURIComponent(new URL(request.url ?? '/', 'http://localhost').pathname);
      const relative = pathname === '/' ? 'index.html' : pathname.replace(/^\/+/, '');
      let filename = path.resolve(outputDir, relative);
      if (filename !== outputDir && !filename.startsWith(`${outputDir}${path.sep}`)) {
        response.writeHead(403).end('Forbidden');
        return;
      }

      let stat = await fs.stat(filename);
      if (stat.isDirectory()) {
        filename = path.join(filename, 'index.html');
        stat = await fs.stat(filename);
      }

      const extension = path.extname(filename).toLowerCase();
      response.setHeader('Content-Type', contentTypes[extension] ?? 'application/octet-stream');
      response.setHeader('Cache-Control', 'no-store');
      if (extension === '.html') {
        response.end(injectReload(await fs.readFile(filename, 'utf8')));
      } else {
        response.setHeader('Content-Length', stat.size);
        createReadStream(filename).pipe(response);
      }
    } catch (error) {
      const status = (error as NodeJS.ErrnoException).code === 'ENOENT' ? 404 : 500;
      response.writeHead(status, { 'Content-Type': 'text/plain; charset=utf-8' });
      response.end(status === 404 ? 'Not found' : 'Internal server error');
    }
  });
  const sockets = new WebSocketServer({ noServer: true });
  server.on('upgrade', (request, socket, head) => {
    if (request.url !== '/__ssg_reload') {
      socket.destroy();
      return;
    }
    sockets.handleUpgrade(request, socket, head, client => sockets.emit('connection', client, request));
  });

  let rebuilding = false;
  let rebuildAgain = false;
  const rebuild = async (): Promise<void> => {
    if (rebuilding) {
      rebuildAgain = true;
      return;
    }
    rebuilding = true;
    do {
      rebuildAgain = false;
      try {
        await buildSite({ contentDir, outputDir, templatesDir });
        for (const client of sockets.clients) {
          if (client.readyState === WebSocket.OPEN) client.send('reload');
        }
      } catch (error) {
        options.io?.stderr.write(`Rebuild failed: ${error instanceof Error ? error.message : String(error)}\n`);
      }
    } while (rebuildAgain);
    rebuilding = false;
  };

  let watcher: FSWatcher | undefined;
  try {
    await listen(server, port, host);
    watcher = chokidar.watch([contentDir, templatesDir], { ignoreInitial: true });
    watcher.on('all', () => void rebuild());
    await new Promise<void>((resolve, reject) => {
      watcher?.once('ready', resolve);
      watcher?.once('error', reject);
    });
  } catch (error) {
    sockets.close();
    server.close();
    throw error;
  }

  const address = server.address();
  const actualPort = typeof address === 'object' && address ? address.port : port;
  return {
    port: actualPort,
    async close(): Promise<void> {
      await watcher?.close();
      for (const client of sockets.clients) client.terminate();
      await new Promise<void>(resolve => sockets.close(() => resolve()));
      await new Promise<void>((resolve, reject) => server.close(error => error ? reject(error) : resolve()));
    }
  };
}
