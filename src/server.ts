import http from 'http';
import fs from 'fs';
import path from 'path';
import { AddressInfo } from 'net';
import { WebSocketServer, WebSocket } from 'ws';
import chokidar from 'chokidar';
import { buildSite } from './generator';

const LIVE_RELOAD_SCRIPT = `
<script>
(function() {
  var protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  var socket = new WebSocket(protocol + '//' + location.host);
  socket.addEventListener('message', function(event) {
    if (event.data === 'reload') {
      window.location.reload();
    }
  });
  socket.addEventListener('close', function() {
    setTimeout(function() { location.reload(); }, 2000);
  });
})();
</script>`;

function injectLiveReload(html: string): string {
  if (html.includes('</body>')) {
    return html.replace('</body>', LIVE_RELOAD_SCRIPT + '</body>');
  }
  return html + LIVE_RELOAD_SCRIPT;
}

const CONTENT_TYPES: Record<string, string> = {
  '.html': 'text/html',
  '.css': 'text/css',
  '.js': 'application/javascript',
  '.json': 'application/json',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
};

export interface ServeOptions {
  content: string;
  output: string;
  templates: string;
  port: number;
}

export interface DevServer {
  close: () => Promise<void>;
  port: number;
}

export function startDevServer(options: ServeOptions): Promise<DevServer> {
  const { content, output, templates, port } = options;

  try {
    buildSite(content, output, templates);
    console.log(`Initial build complete`);
  } catch (err) {
    console.log(`Initial build skipped: ${(err as Error).message}`);
  }

  const server = http.createServer((req, res) => {
    const reqUrl = req.url || '/';

    if (reqUrl === '/ws' || reqUrl.startsWith('/ws?')) {
      res.writeHead(200, { 'Content-Type': 'text/plain' });
      res.end('WebSocket endpoint');
      return;
    }

    const url = new URL(reqUrl, `http://localhost`);
    let filePath = path.join(output, url.pathname === '/' ? '/index.html' : url.pathname);

    if (!path.extname(filePath)) {
      filePath = path.join(filePath, 'index.html');
    }

    const ext = path.extname(filePath).toLowerCase();
    const contentType = CONTENT_TYPES[ext] || 'application/octet-stream';

    try {
      const fileContent = fs.readFileSync(filePath);

      if (ext === '.html') {
        const html = injectLiveReload(fileContent.toString('utf-8'));
        res.writeHead(200, { 'Content-Type': 'text/html' });
        res.end(html);
        return;
      }

      res.writeHead(200, { 'Content-Type': contentType });
      res.end(fileContent);
    } catch {
      const origExt = path.extname(reqUrl || '').toLowerCase();
      if (!origExt) {
        try {
          const indexPath = path.join(output, 'index.html');
          const html = injectLiveReload(fs.readFileSync(indexPath, 'utf-8'));
          res.writeHead(200, { 'Content-Type': 'text/html' });
          res.end(html);
          return;
        } catch {
          // fall through to 404
        }
      }
      res.writeHead(404, { 'Content-Type': 'text/plain' });
      res.end('Not Found');
    }
  });

  const wss = new WebSocketServer({ server });
  const clients = new Set<WebSocket>();

  wss.on('connection', (ws) => {
    clients.add(ws);
    ws.on('close', () => clients.delete(ws));
  });

  const watchPaths: string[] = [];
  if (fs.existsSync(content)) watchPaths.push(content);
  if (fs.existsSync(templates)) watchPaths.push(templates);

  const watcher = chokidar.watch(watchPaths, {
    ignoreInitial: true,
  });

  let rebuildTimeout: ReturnType<typeof setTimeout> | null = null;

  function triggerRebuild() {
    if (rebuildTimeout) clearTimeout(rebuildTimeout);
    rebuildTimeout = setTimeout(() => {
      try {
        console.log('Rebuilding...');
        buildSite(content, output, templates);
        console.log('Rebuild complete');

        for (const client of clients) {
          if (client.readyState === WebSocket.OPEN) {
            client.send('reload');
          }
        }
      } catch (err) {
        console.error('Rebuild error:', (err as Error).message);
      }
    }, 200);
  }

  watcher.on('change', triggerRebuild);
  watcher.on('add', triggerRebuild);
  watcher.on('unlink', triggerRebuild);

  return new Promise((resolve, reject) => {
    let chokidarReady = watchPaths.length === 0;

    watcher.on('ready', () => {
      chokidarReady = true;
    });

    server.listen(port, () => {
      const actualPort = (server.address() as AddressInfo).port;
      console.log(`Dev server running at http://localhost:${actualPort}`);

      function resolveWhenReady() {
        if (chokidarReady) {
          resolve({
            port: actualPort,
            close: async () => {
              if (rebuildTimeout) clearTimeout(rebuildTimeout);
              await watcher.close();
              for (const client of clients) {
                client.terminate();
              }
              wss.close();
              await new Promise<void>((resolveClose) => {
                server.close(() => resolveClose());
              });
            },
          });
        } else {
          setTimeout(resolveWhenReady, 10);
        }
      }

      resolveWhenReady();
    });

    server.on('error', reject);
  });
}
