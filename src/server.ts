import { createReadStream, promises as fs } from 'node:fs';
import { createServer, type ServerResponse } from 'node:http';
import path from 'node:path';
import chokidar, { type FSWatcher } from 'chokidar';
import { WebSocket, WebSocketServer } from 'ws';
import { buildSite, type BuildOptions } from './index.js';

const reloadScript = `<script>(function(){var protocol=location.protocol==='https:'?'wss://':'ws://';var socket=new WebSocket(protocol+location.host+'/__ssg_reload');socket.addEventListener('message',function(event){if(event.data==='reload')location.reload();});})();</script>`;

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
  '.webp': 'image/webp',
};

export interface ServeOptions extends BuildOptions {
  port?: number;
}

export interface DevServer {
  port: number;
  close(): Promise<void>;
}

function injectReloadScript(html: string): string {
  const bodyEnd = html.toLowerCase().lastIndexOf('</body>');
  return bodyEnd === -1
    ? `${html}${reloadScript}`
    : `${html.slice(0, bodyEnd)}${reloadScript}${html.slice(bodyEnd)}`;
}

function sendError(response: ServerResponse, status: number): void {
  response.writeHead(status, { 'Content-Type': 'text/plain; charset=utf-8' });
  response.end(status === 404 ? 'Not Found' : 'Internal Server Error');
}

async function serveFile(outputDir: string, requestUrl: string, response: ServerResponse): Promise<void> {
  let pathname: string;
  try {
    pathname = decodeURIComponent(new URL(requestUrl, 'http://localhost').pathname);
  } catch {
    sendError(response, 404);
    return;
  }

  const requested = pathname.endsWith('/') ? `${pathname}index.html` : pathname;
  const filePath = path.resolve(outputDir, `.${requested}`);
  const relative = path.relative(outputDir, filePath);
  if (relative === '..' || relative.startsWith(`..${path.sep}`) || path.isAbsolute(relative)) {
    sendError(response, 404);
    return;
  }

  try {
    const stat = await fs.stat(filePath);
    if (!stat.isFile()) {
      sendError(response, 404);
      return;
    }
    const extension = path.extname(filePath).toLowerCase();
    response.setHeader('Content-Type', contentTypes[extension] ?? 'application/octet-stream');
    response.setHeader('Cache-Control', 'no-store');
    if (extension === '.html') {
      response.end(injectReloadScript(await fs.readFile(filePath, 'utf8')));
      return;
    }
    createReadStream(filePath)
      .on('error', () => sendError(response, 500))
      .pipe(response);
  } catch (error) {
    sendError(response, (error as NodeJS.ErrnoException).code === 'ENOENT' ? 404 : 500);
  }
}

export async function startDevServer(options: ServeOptions = {}): Promise<DevServer> {
  const contentDir = path.resolve(options.contentDir ?? './content');
  const templatesDir = path.resolve(options.templatesDir ?? './templates');
  const outputDir = path.resolve(options.outputDir ?? './dist');
  const port = options.port ?? 3000;

  await buildSite({ contentDir, templatesDir, outputDir });

  const server = createServer((request, response) => {
    void serveFile(outputDir, request.url ?? '/', response);
  });
  const webSockets = new WebSocketServer({ server, path: '/__ssg_reload' });
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
        await buildSite({ contentDir, templatesDir, outputDir });
        for (const client of webSockets.clients) {
          if (client.readyState === WebSocket.OPEN) client.send('reload');
        }
      } catch (error) {
        process.stderr.write(`Rebuild failed: ${error instanceof Error ? error.message : String(error)}\n`);
      }
    } while (rebuildPending);
    rebuilding = false;
  };

  const watcher: FSWatcher = chokidar.watch([contentDir, templatesDir], {
    ignoreInitial: true,
  });
  watcher.on('all', () => void rebuild());
  const watcherReady = new Promise<void>((resolve) => watcher.once('ready', resolve));

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
    webSockets.close();
    throw error;
  }
  await watcherReady;

  const address = server.address();
  const listeningPort = typeof address === 'object' && address ? address.port : port;
  return {
    port: listeningPort,
    async close(): Promise<void> {
      await watcher.close();
      for (const client of webSockets.clients) client.terminate();
      await new Promise<void>((resolve) => webSockets.close(() => resolve()));
      await new Promise<void>((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
    },
  };
}
