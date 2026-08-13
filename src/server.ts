import { createReadStream, promises as fs } from 'node:fs';
import { createServer, type Server } from 'node:http';
import path from 'node:path';
import chokidar, { type FSWatcher } from 'chokidar';
import { WebSocket, WebSocketServer } from 'ws';
import { buildSite, type BuildOptions } from './index';

export interface ServeOptions extends BuildOptions {
  port?: number;
}

export interface DevelopmentServer {
  port: number;
  close(): Promise<void>;
}

const LIVE_RELOAD_SCRIPT = `<script>
(() => {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const socket = new WebSocket(protocol + '//' + location.host + '/__ssg_reload');
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
  const closingBody = html.search(/<\/body\s*>/i);
  return closingBody === -1
    ? `${html}\n${LIVE_RELOAD_SCRIPT}\n`
    : `${html.slice(0, closingBody)}${LIVE_RELOAD_SCRIPT}\n${html.slice(closingBody)}`;
}

function requestedFile(outputDirectory: string, requestUrl = '/'): string | undefined {
  let pathname: string;
  try {
    pathname = decodeURIComponent(new URL(requestUrl, 'http://localhost').pathname);
  } catch {
    return undefined;
  }
  const relative = pathname.replace(/^\/+/, '') || 'index.html';
  const root = path.resolve(outputDirectory);
  const resolved = path.resolve(root, relative);
  return resolved === root || resolved.startsWith(`${root}${path.sep}`) ? resolved : undefined;
}

async function listen(server: Server, port: number): Promise<number> {
  await new Promise<void>((resolve, reject) => {
    server.once('error', reject);
    server.listen(port, 'localhost', () => {
      server.off('error', reject);
      resolve();
    });
  });
  const address = server.address();
  if (!address || typeof address === 'string') throw new Error('Unable to determine server port');
  return address.port;
}

export async function startDevelopmentServer(options: ServeOptions = {}): Promise<DevelopmentServer> {
  const outputDirectory = path.resolve(options.output ?? './dist');
  const contentDirectory = path.resolve(options.content ?? './content');
  const templatesDirectory = path.resolve(options.templates ?? './templates');
  const port = options.port ?? 3000;

  await buildSite({ content: contentDirectory, output: outputDirectory, templates: templatesDirectory });

  const server = createServer(async (request, response) => {
    try {
      let file = requestedFile(outputDirectory, request.url);
      if (!file) {
        response.writeHead(404).end('Not found');
        return;
      }
      let stat;
      try {
        stat = await fs.stat(file);
        if (stat.isDirectory()) {
          file = path.join(file, 'index.html');
          stat = await fs.stat(file);
        }
      } catch {
        response.writeHead(404).end('Not found');
        return;
      }
      if (!stat.isFile()) {
        response.writeHead(404).end('Not found');
        return;
      }

      const extension = path.extname(file).toLowerCase();
      response.setHeader('Content-Type', CONTENT_TYPES[extension] ?? 'application/octet-stream');
      if (extension === '.html') {
        response.end(injectLiveReload(await fs.readFile(file, 'utf8')));
      } else {
        createReadStream(file).on('error', () => response.destroy()).pipe(response);
      }
    } catch (error) {
      response.writeHead(500).end('Internal server error');
      process.stderr.write(`Server error: ${error instanceof Error ? error.message : String(error)}\n`);
    }
  });
  const sockets = new WebSocketServer({ server, path: '/__ssg_reload' });
  let watcher: FSWatcher | undefined;
  let rebuild = Promise.resolve();

  try {
    const actualPort = await listen(server, port);
    watcher = chokidar.watch([contentDirectory, templatesDirectory], { ignoreInitial: true });
    await new Promise<void>((resolve, reject) => {
      watcher?.once('ready', resolve);
      watcher?.once('error', reject);
    });
    watcher.on('all', () => {
      rebuild = rebuild.then(async () => {
        try {
          await buildSite({ content: contentDirectory, output: outputDirectory, templates: templatesDirectory });
          for (const client of sockets.clients) {
            if (client.readyState === WebSocket.OPEN) client.send('reload');
          }
        } catch (error) {
          process.stderr.write(`Rebuild failed: ${error instanceof Error ? error.message : String(error)}\n`);
        }
      });
    });

    return {
      port: actualPort,
      async close() {
        await watcher?.close();
        await rebuild;
        for (const client of sockets.clients) client.terminate();
        await new Promise<void>((resolve, reject) => {
          sockets.close((error) => error ? reject(error) : resolve());
        });
        await new Promise<void>((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
      },
    };
  } catch (error) {
    await watcher?.close();
    sockets.close();
    server.close();
    throw error;
  }
}
