import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { URL } from 'node:url';
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

const reloadScript = `<script>(function(){var socket=new WebSocket((location.protocol==='https:'?'wss://':'ws://')+location.host+'/__ssg_reload');socket.onmessage=function(event){if(event.data==='reload')location.reload()};socket.onclose=function(){setTimeout(function(){location.reload()},1000)}})();</script>`;

function injectReloadScript(content: string): string {
  const marker = /<\/body\s*>/i;
  return marker.test(content) ? content.replace(marker, `${reloadScript}</body>`) : `${content}${reloadScript}`;
}

function contentType(filename: string): string {
  if (filename.endsWith('.html')) return 'text/html; charset=utf-8';
  if (filename.endsWith('.css')) return 'text/css; charset=utf-8';
  if (filename.endsWith('.js')) return 'text/javascript; charset=utf-8';
  if (filename.endsWith('.json')) return 'application/json; charset=utf-8';
  return 'application/octet-stream';
}

export function startDevServer(options: ServeOptions = {}): Promise<DevServer> {
  const outputDir = path.resolve(options.outputDir ?? './dist');
  const contentDir = path.resolve(options.contentDir ?? './content');
  const templatesDir = path.resolve(options.templatesDir ?? options.templateDir ?? './templates');
  const port = options.port ?? 3000;
  const host = options.host ?? 'localhost';
  const sockets = new WebSocketServer({ noServer: true });

  buildSite({ ...options, contentDir, outputDir, templatesDir });
  const server = http.createServer((request, response) => {
    try {
      const requestPath = decodeURIComponent(new URL(request.url ?? '/', `http://${host}`).pathname);
      const relative = requestPath === '/' ? 'index.html' : requestPath.replace(/^\/+/, '');
      const filename = path.resolve(outputDir, relative);
      if (filename !== outputDir && !filename.startsWith(`${outputDir}${path.sep}`)) {
        response.writeHead(403).end('Forbidden');
        return;
      }
      if (!fs.existsSync(filename) || !fs.statSync(filename).isFile()) {
        response.writeHead(404).end('Not found');
        return;
      }
      let body = fs.readFileSync(filename);
      if (filename.endsWith('.html')) body = Buffer.from(injectReloadScript(body.toString('utf8')));
      response.writeHead(200, { 'Content-Type': contentType(filename) }).end(body);
    } catch {
      response.writeHead(400).end('Bad request');
    }
  });
  server.on('upgrade', (request, socket, head) => {
    if (request.url !== '/__ssg_reload') {
      socket.destroy();
      return;
    }
    sockets.handleUpgrade(request, socket, head, (client) => sockets.emit('connection', client, request));
  });
  sockets.on('connection', (client) => client.on('error', () => client.close()));

  let rebuildTimer: NodeJS.Timeout | undefined;
  const watcher = chokidar.watch([contentDir, templatesDir], { ignoreInitial: true });
  watcher.on('all', () => {
    if (rebuildTimer) clearTimeout(rebuildTimer);
    rebuildTimer = setTimeout(() => {
      try {
        buildSite({ ...options, contentDir, outputDir, templatesDir });
        for (const client of sockets.clients) if (client.readyState === 1) client.send('reload');
      } catch (error) {
        console.error(error instanceof Error ? error.message : error);
      }
    }, 50);
  });

  return new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(port, host, () => {
      server.removeListener('error', reject);
      resolve({
        server,
        watcher,
        close: async () => {
          if (rebuildTimer) clearTimeout(rebuildTimer);
          await watcher.close();
          for (const client of sockets.clients) client.terminate();
          sockets.close();
          await new Promise<void>((done) => server.close(() => done()));
        }
      });
    });
  });
}
