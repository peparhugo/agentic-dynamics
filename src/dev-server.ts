import { createReadStream } from 'node:fs';
import { readFile, stat } from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';
import { URL } from 'node:url';
import chokidar, { FSWatcher } from 'chokidar';
import { WebSocketServer } from 'ws';
import { buildSite, BuildOptions } from './generator';

export interface DevServerOptions extends BuildOptions {
  port?: number;
}

export interface DevServer {
  server: http.Server;
  watcher: FSWatcher;
  close: () => Promise<void>;
}

const liveReloadScript = `<script>(function(){var socket=new WebSocket('ws://'+location.host);socket.onmessage=function(event){if(event.data==='reload')location.reload();};})();</script>`;

function injectLiveReload(html: string): string {
  if (html.includes("new WebSocket('ws://'+location.host)")) return html;
  const tag = html.match(/<\/body\s*>/i) || html.match(/<\/html\s*>/i);
  return tag ? html.replace(tag[0], `${liveReloadScript}${tag[0]}`) : `${html}${liveReloadScript}`;
}

function contentType(filePath: string): string {
  const types: Record<string, string> = {
    '.css': 'text/css', '.js': 'application/javascript', '.json': 'application/json',
    '.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
    '.gif': 'image/gif', '.ico': 'image/x-icon'
  };
  return types[path.extname(filePath).toLowerCase()] || 'application/octet-stream';
}

async function serveFile(request: http.IncomingMessage, response: http.ServerResponse, outputDir: string): Promise<void> {
  try {
    const requestPath = decodeURIComponent(new URL(request.url || '/', 'http://localhost').pathname);
    const relativePath = requestPath === '/' ? 'index.html' : requestPath.replace(/^\/+/, '');
    const filePath = path.resolve(outputDir, relativePath);
    if (filePath !== outputDir && !filePath.startsWith(`${outputDir}${path.sep}`)) {
      response.writeHead(403).end('Forbidden');
      return;
    }
    const fileStats = await stat(filePath);
    if (!fileStats.isFile()) throw new Error('Not a file');
    response.setHeader('Content-Type', contentType(filePath));
    if (path.extname(filePath).toLowerCase() === '.html') {
      if (request.method === 'HEAD') response.end();
      else response.end(injectLiveReload(await readFile(filePath, 'utf8')));
    } else {
      if (request.method === 'HEAD') response.end();
      else createReadStream(filePath).pipe(response);
    }
  } catch {
    response.writeHead(404).end('Not found');
  }
}

export async function startDevServer(options: DevServerOptions = {}): Promise<DevServer> {
  const outputDir = path.resolve(options.outputDir || './dist');
  const contentDir = path.resolve(options.contentDir || './content');
  const templatesDir = path.resolve(options.templatesDir || './templates');
  await buildSite(options);

  const clients = new WebSocketServer({ noServer: true });
  const server = http.createServer((request, response) => {
    if (request.method !== 'GET' && request.method !== 'HEAD') {
      response.writeHead(405).end('Method not allowed');
      return;
    }
    void serveFile(request, response, outputDir);
  });
  server.on('upgrade', (request, socket, head) => {
    clients.handleUpgrade(request, socket, head, (client) => clients.emit('connection', client, request));
  });

  let rebuild = Promise.resolve();
  const watcher = chokidar.watch([contentDir, templatesDir], { ignoreInitial: true });
  const rebuildSite = () => {
    rebuild = rebuild.then(async () => {
      await buildSite(options);
      clients.clients.forEach((client) => client.send('reload'));
    }).catch((error: unknown) => {
      console.error(`Build failed: ${error instanceof Error ? error.message : error}`);
    });
  };
  watcher.on('add', rebuildSite).on('change', rebuildSite).on('unlink', rebuildSite);

  await new Promise<void>((resolve, reject) => {
    server.once('error', reject);
    server.listen(options.port ?? 3000, '127.0.0.1', () => {
      server.removeListener('error', reject);
      resolve();
    });
  });

  return {
    server,
    watcher,
    close: async () => {
      await watcher.close();
      clients.clients.forEach((client) => client.terminate());
      clients.close();
      await new Promise<void>((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
    }
  };
}
