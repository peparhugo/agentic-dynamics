import http from 'http';
import fs from 'fs';
import path from 'path';
import chokidar from 'chokidar';
import { WebSocketServer, WebSocket } from 'ws';
import { generateSite } from './generator';

export const LIVE_RELOAD_SCRIPT = `<script>
(function () {
  var ws = new WebSocket('ws://' + location.host);
  ws.onmessage = function (msg) {
    if (msg.data === 'reload') location.reload();
  };
})();
</script>`;

export interface ServerOptions {
  content: string;
  output: string;
  templates?: string;
  port: number;
}

export function injectLiveReload(html: string): string {
  if (html.includes('</body>')) {
    return html.replace('</body>', `${LIVE_RELOAD_SCRIPT}</body>`);
  }
  return html + LIVE_RELOAD_SCRIPT;
}

const mimeTypes: Record<string, string> = {
  '.html': 'text/html',
  '.css': 'text/css',
  '.js': 'application/javascript',
  '.json': 'application/json',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.gif': 'image/gif',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
};

export function createServer(options: ServerOptions): http.Server {
  const { content, output, templates } = options;

  const server = http.createServer((req, res) => {
    const urlPath = req.url === '/' ? '/index.html' : req.url || '/';
    const filePath = path.join(output, urlPath);

    const resolved = path.resolve(filePath);
    if (!resolved.startsWith(path.resolve(output))) {
      res.writeHead(403);
      res.end('Forbidden');
      return;
    }

    if (!fs.existsSync(filePath) || fs.statSync(filePath).isDirectory()) {
      res.writeHead(404, { 'Content-Type': 'text/plain' });
      res.end('Not Found');
      return;
    }

    const ext = path.extname(filePath).toLowerCase();
    const contentType = mimeTypes[ext] || 'application/octet-stream';

    try {
      if (ext === '.html') {
        let content = fs.readFileSync(filePath, 'utf-8');
        content = injectLiveReload(content);
        res.writeHead(200, { 'Content-Type': contentType });
        res.end(content);
      } else {
        const content = fs.readFileSync(filePath);
        res.writeHead(200, { 'Content-Type': contentType });
        res.end(content);
      }
    } catch {
      res.writeHead(500);
      res.end('Internal Server Error');
    }
  });

  const wss = new WebSocketServer({ server });
  const clients = new Set<WebSocket>();

  wss.on('connection', (ws) => {
    clients.add(ws);
    ws.on('close', () => clients.delete(ws));
  });

  function notifyClients() {
    for (const client of clients) {
      if (client.readyState === WebSocket.OPEN) {
        client.send('reload');
      }
    }
  }

  const watchDirs: string[] = [content];
  if (templates && fs.existsSync(templates)) {
    watchDirs.push(templates);
  }

  const watcher = chokidar.watch(watchDirs, { ignoreInitial: true });

  let buildTimeout: ReturnType<typeof setTimeout> | null = null;

  watcher.on('all', () => {
    if (buildTimeout) clearTimeout(buildTimeout);
    buildTimeout = setTimeout(() => {
      generateSite(content, output, templates);
      notifyClients();
    }, 100);
  });

  server.on('close', () => {
    watcher.close();
    wss.close();
  });

  return server;
}

export function startServer(options: ServerOptions): http.Server {
  generateSite(options.content, options.output, options.templates);

  const server = createServer(options);

  server.listen(options.port, () => {
    console.log(`Dev server running at http://localhost:${options.port}`);
  });

  return server;
}
