import { createReadStream, promises as fs } from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import chokidar, { FSWatcher } from 'chokidar';
import { WebSocketServer } from 'ws';
import { buildSite, BuildOptions } from './generator';

export interface ServeOptions extends BuildOptions {
  port?: number;
  host?: string;
}

export interface DevServer {
  server: http.Server;
  watcher: FSWatcher;
  close(): Promise<void>;
}

const reloadScript = `<script>(function(){var socket=new WebSocket((location.protocol==='https:'?'wss://':'ws://')+location.host+'/__ssg_reload');socket.onmessage=function(event){if(event.data==='reload') location.reload();};})();</script>`;

function contentType(filePath: string): string {
  const types: Record<string, string> = {
    '.html': 'text/html; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.js': 'text/javascript; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.svg': 'image/svg+xml',
  };
  return types[path.extname(filePath).toLowerCase()] ?? 'application/octet-stream';
}

async function serveFile(request: http.IncomingMessage, response: http.ServerResponse, outputDir: string): Promise<void> {
  let requested: string;
  try {
    requested = decodeURIComponent((request.url ?? '/').split('?')[0]);
  } catch {
    response.writeHead(400);
    response.end('Bad request');
    return;
  }
  const relative = requested === '/' ? 'index.html' : requested.replace(/^\/+/, '');
  const target = path.resolve(outputDir, relative);
  if (target !== outputDir && !target.startsWith(`${outputDir}${path.sep}`)) {
    response.writeHead(403);
    response.end('Forbidden');
    return;
  }
  try {
    const stats = await fs.stat(target);
    if (!stats.isFile()) throw new Error('Not a file');
    response.writeHead(200, { 'Content-Type': contentType(target) });
    if (path.extname(target).toLowerCase() === '.html') {
      const html = await fs.readFile(target, 'utf8');
      response.end(/<\/body>/i.test(html) ? html.replace(/<\/body>/i, `${reloadScript}</body>`) : `${html}${reloadScript}`);
    } else {
      createReadStream(target).pipe(response);
    }
  } catch {
    response.writeHead(404);
    response.end('Not found');
  }
}

export async function startDevServer(options: ServeOptions = {}): Promise<DevServer> {
  const outputDir = path.resolve(options.outputDir ?? './dist');
  const contentDir = path.resolve(options.contentDir ?? './content');
  const templatesDir = path.resolve(options.templatesDir ?? './templates');
  const port = options.port ?? 3000;
  const host = options.host ?? 'localhost';

  await buildSite(options);
  const server = http.createServer((request, response) => {
    void serveFile(request, response, outputDir);
  });
  const sockets = new WebSocketServer({ server, path: '/__ssg_reload' });
  let rebuilding = false;
  let queued = false;
  const rebuild = async (): Promise<void> => {
    if (rebuilding) {
      queued = true;
      return;
    }
    rebuilding = true;
    try {
      await buildSite(options);
      sockets.clients.forEach((client) => client.send('reload'));
    } catch (error) {
      console.error(`Build failed: ${error instanceof Error ? error.message : error}`);
    } finally {
      rebuilding = false;
      if (queued) {
        queued = false;
        void rebuild();
      }
    }
  };
  const watcher = chokidar.watch([contentDir, templatesDir], { ignoreInitial: true });
  watcher.on('add', () => void rebuild()).on('change', () => void rebuild()).on('unlink', () => void rebuild());

  await new Promise<void>((resolve, reject) => {
    server.once('error', reject);
    server.listen(port, host, () => {
      server.removeListener('error', reject);
      resolve();
    });
  });

  return {
    server,
    watcher,
    close: async () => {
      await watcher.close();
      sockets.close();
      await new Promise<void>((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
    },
  };
}
