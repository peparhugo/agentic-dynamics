import { promises as fs } from 'node:fs';
import { createServer } from 'node:http';
import path from 'node:path';
import chokidar, { type FSWatcher } from 'chokidar';
import { WebSocket, WebSocketServer } from 'ws';
import { buildSite, type BuildOptions } from './index';

export interface ServeOptions extends BuildOptions {
  port?: number;
  host?: string;
}

export interface DevServer {
  port: number;
  close(): Promise<void>;
}

const liveReloadScript = `<script>
(() => {
  const socket = new WebSocket(` + "`ws://${location.host}`" + `);
  socket.addEventListener('message', (event) => {
    if (event.data === 'reload') location.reload();
  });
})();
</script>`;

const contentTypes: Record<string, string> = {
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
  '.webp': 'image/webp'
};

function injectLiveReload(html: string): string {
  const closingBody = /<\/body\s*>/i;
  return closingBody.test(html)
    ? html.replace(closingBody, `${liveReloadScript}\n</body>`)
    : `${html}\n${liveReloadScript}\n`;
}

function requestFile(outputDir: string, requestUrl: string): string | undefined {
  let pathname: string;
  try {
    pathname = decodeURIComponent(new URL(requestUrl, 'http://localhost').pathname);
  } catch {
    return undefined;
  }

  const relative = pathname.endsWith('/') ? `${pathname}index.html` : pathname;
  const file = path.resolve(outputDir, `.${relative}`);
  const withinOutput = path.relative(outputDir, file);
  return withinOutput.startsWith(`..${path.sep}`) || path.isAbsolute(withinOutput) ? undefined : file;
}

export async function startDevServer(options: ServeOptions = {}): Promise<DevServer> {
  const contentDir = path.resolve(options.contentDir ?? './content');
  const outputDir = path.resolve(options.outputDir ?? './dist');
  const templatesDir = path.resolve(options.templatesDir ?? './templates');
  const port = options.port ?? 3000;
  const host = options.host ?? 'localhost';
  const buildOptions = { contentDir, outputDir, templatesDir };

  await buildSite(buildOptions);

  const server = createServer(async (request, response) => {
    if (request.method !== 'GET' && request.method !== 'HEAD') {
      response.writeHead(405, { Allow: 'GET, HEAD' }).end();
      return;
    }

    const file = requestFile(outputDir, request.url ?? '/');
    if (!file) {
      response.writeHead(400).end('Bad request');
      return;
    }

    try {
      let data = await fs.readFile(file);
      const extension = path.extname(file).toLowerCase();
      if (extension === '.html') {
        data = Buffer.from(injectLiveReload(data.toString('utf8')));
      }
      response.writeHead(200, {
        'Content-Type': contentTypes[extension] ?? 'application/octet-stream',
        'Content-Length': data.byteLength,
        'Cache-Control': 'no-store'
      });
      response.end(request.method === 'HEAD' ? undefined : data);
    } catch (error) {
      const status = (error as NodeJS.ErrnoException).code === 'ENOENT' ? 404 : 500;
      response.writeHead(status).end(status === 404 ? 'Not found' : 'Server error');
    }
  });
  const sockets = new WebSocketServer({ server });

  let rebuild = Promise.resolve();
  const watcher: FSWatcher = chokidar.watch([contentDir, templatesDir], {
    ignoreInitial: true
  });
  const watcherReady = new Promise<void>((resolve) => watcher.once('ready', resolve));
  watcher.on('all', () => {
    rebuild = rebuild.then(async () => {
      try {
        await buildSite(buildOptions);
        for (const client of sockets.clients) {
          if (client.readyState === WebSocket.OPEN) client.send('reload');
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        process.stderr.write(`Rebuild failed: ${message}\n`);
      }
    });
  });

  try {
    await new Promise<void>((resolve, reject) => {
      server.once('error', reject);
      server.listen(port, host, () => {
        server.off('error', reject);
        resolve();
      });
    });
    await watcherReady;
  } catch (error) {
    await watcher.close();
    sockets.close();
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
        sockets.close(() => {
          server.close((error) => error ? reject(error) : resolve());
        });
      });
    }
  };
}
