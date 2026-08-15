import http from 'node:http';
import fs from 'node:fs/promises';
import path from 'node:path';
import { WebSocketServer } from 'ws';
import chokidar, { FSWatcher } from 'chokidar';
import { buildSite } from './generator';

export interface ServeOptions {
  content?: string;
  output?: string;
  templates?: string;
  port?: number;
  host?: string;
}

export interface RunningServer {
  server: http.Server;
  watcher: FSWatcher;
  close: () => Promise<void>;
}

const reloadScript = `<script>(function(){var socket;function connect(){socket=new WebSocket((location.protocol==='https:'?'wss://':'ws://')+location.host);socket.onmessage=function(event){if(event.data==='reload')location.reload()};socket.onclose=function(){setTimeout(connect,500)}}connect()})();</script>`;

function contentType(file: string): string {
  if (file.endsWith('.html')) return 'text/html; charset=utf-8';
  if (file.endsWith('.css')) return 'text/css; charset=utf-8';
  if (file.endsWith('.js')) return 'text/javascript; charset=utf-8';
  if (file.endsWith('.json')) return 'application/json; charset=utf-8';
  return 'application/octet-stream';
}

function injectReload(html: string): string {
  const closingBody = html.search(/<\/body\s*>/i);
  return closingBody < 0 ? `${html}${reloadScript}` : `${html.slice(0, closingBody)}${reloadScript}${html.slice(closingBody)}`;
}

async function serveFile(request: http.IncomingMessage, response: http.ServerResponse, output: string): Promise<void> {
  if (!request.url) {
    response.writeHead(400).end('Bad Request');
    return;
  }
  let pathname: string;
  try {
    pathname = decodeURIComponent(new URL(request.url, 'http://localhost').pathname);
  } catch {
    response.writeHead(400).end('Bad Request');
    return;
  }
  const relative = pathname === '/' ? 'index.html' : pathname.replace(/^\/+/, '');
  const root = path.resolve(output);
  const file = path.resolve(root, relative);
  if (file !== root && !file.startsWith(`${root}${path.sep}`)) {
    response.writeHead(403).end('Forbidden');
    return;
  }
  try {
    let body = await fs.readFile(file);
    if (file.endsWith('.html')) body = Buffer.from(injectReload(body.toString('utf8')));
    response.writeHead(200, { 'Content-Type': contentType(file), 'Content-Length': body.length });
    response.end(body);
  } catch (error) {
    const code = (error as NodeJS.ErrnoException).code;
    response.writeHead(code === 'ENOENT' ? 404 : 500).end(code === 'ENOENT' ? 'Not Found' : 'Internal Server Error');
  }
}

export async function startServer(options: ServeOptions = {}): Promise<RunningServer> {
  const content = options.content ?? './content';
  const output = options.output ?? './dist';
  const templates = options.templates ?? './templates';
  const port = options.port ?? 3000;
  const host = options.host ?? 'localhost';
  if (!Number.isInteger(port) || port < 0 || port > 65535) throw new Error(`Invalid port: ${port}`);

  await buildSite(content, output, templates);
  const server = http.createServer((request, response) => {
    void serveFile(request, response, output);
  });
  const sockets = new WebSocketServer({ server });
  const watcher = chokidar.watch([content, templates], { ignoreInitial: true });
  let rebuilding = false;
  let queued = false;

  const rebuild = async (): Promise<void> => {
    if (rebuilding) {
      queued = true;
      return;
    }
    rebuilding = true;
    try {
      await buildSite(content, output, templates);
      sockets.clients.forEach((client) => {
        if (client.readyState === client.OPEN) client.send('reload');
      });
    } catch (error) {
      process.stderr.write(`Rebuild failed: ${error instanceof Error ? error.message : String(error)}\n`);
    } finally {
      rebuilding = false;
      if (queued) {
        queued = false;
        void rebuild();
      }
    }
  };
  watcher.on('add', () => void rebuild()).on('change', () => void rebuild()).on('unlink', () => void rebuild());

  await new Promise<void>((resolve, reject) => {
    const onError = (error: Error) => reject(error);
    server.once('error', onError);
    server.listen(port, host, () => {
      server.removeListener('error', onError);
      resolve();
    });
  });
  process.stdout.write(`Serving ${output} at http://${host}:${port}\n`);

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
