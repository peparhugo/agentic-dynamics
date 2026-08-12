import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import chokidar, { FSWatcher } from 'chokidar';
import { WebSocketServer } from 'ws';
import { buildSite, BuildOptions } from './index';

export interface ServeOptions extends BuildOptions {
  port?: number;
  host?: string;
}

export interface DevServer {
  server: http.Server;
  watcher: FSWatcher;
  close(): Promise<void>;
}

const liveReloadScript = `
<script>
(function () {
  var protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  var socket;
  function connect() {
    socket = new WebSocket(protocol + '//' + location.host);
    socket.onmessage = function (event) {
      if (event.data === 'reload') location.reload();
    };
    socket.onclose = function () { setTimeout(connect, 500); };
  }
  connect();
}());
</script>`;

function injectLiveReload(html: string): string {
  const closingBody = html.match(/<\/body\s*>/i);
  if (!closingBody || closingBody.index === undefined) return `${html}${liveReloadScript}`;
  return `${html.slice(0, closingBody.index)}${liveReloadScript}${html.slice(closingBody.index)}`;
}

function contentType(file: string): string {
  if (file.endsWith('.html')) return 'text/html; charset=utf-8';
  if (file.endsWith('.css')) return 'text/css; charset=utf-8';
  if (file.endsWith('.js')) return 'text/javascript; charset=utf-8';
  if (file.endsWith('.json')) return 'application/json; charset=utf-8';
  return 'application/octet-stream';
}

function safeFile(outputDir: string, requestPath: string): string | undefined {
  let relative = decodeURIComponent(requestPath.split('?')[0]);
  if (relative === '/') relative = '/index.html';
  const root = path.resolve(outputDir);
  const file = path.resolve(root, `.${relative}`);
  return file === root || file.startsWith(`${root}${path.sep}`) ? file : undefined;
}

export function startDevServer(options: ServeOptions = {}): Promise<DevServer> {
  const outputDir = path.resolve(options.outputDir ?? './dist');
  const contentDir = path.resolve(options.contentDir ?? './content');
  const templatesDir = path.resolve(options.templatesDir ?? './templates');
  const port = options.port ?? 3000;
  const host = options.host ?? 'localhost';

  buildSite({ ...options, outputDir, contentDir, templatesDir });

  const webSocketServer = new WebSocketServer({ noServer: true });
  const server = http.createServer((request, response) => {
    try {
      const file = safeFile(outputDir, request.url ?? '/');
      if (!file || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
        response.writeHead(404);
        response.end('Not found');
        return;
      }
      let body = fs.readFileSync(file);
      if (file.endsWith('.html')) body = Buffer.from(injectLiveReload(body.toString('utf8')));
      response.writeHead(200, { 'Content-Type': contentType(file) });
      response.end(body);
    } catch {
      response.writeHead(400);
      response.end('Bad request');
    }
  });

  server.on('upgrade', (request, socket, head) => {
    webSocketServer.handleUpgrade(request, socket, head, (client) => {
      webSocketServer.emit('connection', client, request);
    });
  });

  webSocketServer.on('connection', (client) => {
    client.send('connected');
  });

  let rebuilding = false;
  let queued = false;
  const rebuild = () => {
    if (rebuilding) {
      queued = true;
      return;
    }
    rebuilding = true;
    try {
      buildSite({ ...options, outputDir, contentDir, templatesDir });
      webSocketServer.clients.forEach((client) => client.send('reload'));
    } catch (error) {
      process.stderr.write(`Build failed: ${error instanceof Error ? error.message : String(error)}\n`);
    } finally {
      rebuilding = false;
      if (queued) {
        queued = false;
        rebuild();
      }
    }
  };
  const watcher = chokidar.watch([contentDir, templatesDir], { ignoreInitial: true });
  watcher.on('all', rebuild);

  return new Promise((resolve, reject) => {
    const onError = (error: Error) => reject(error);
    server.once('error', onError);
    server.listen(port, host, () => {
      server.removeListener('error', onError);
      resolve({
        server,
        watcher,
        async close() {
          await watcher.close();
          webSocketServer.close();
          await new Promise<void>((done) => server.close(() => done()));
        },
      });
    });
  });
}

export { injectLiveReload };
