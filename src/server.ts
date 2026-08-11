import http from 'http';
import fs from 'fs';
import path from 'path';
import chokidar from 'chokidar';
import { WebSocketServer, WebSocket } from 'ws';
import { parseDirectory } from './parser';
import { generateSite } from './generator';

const RELOAD_SCRIPT = `
<script>
(function() {
  var ws = new WebSocket('ws://' + location.host);
  ws.onmessage = function(msg) {
    if (msg.data === 'reload') location.reload();
  };
  ws.onclose = function() {
    setTimeout(function() {
      var ws2 = new WebSocket('ws://' + location.host);
      ws2.onmessage = function(msg) {
        if (msg.data === 'reload') location.reload();
      };
      ws2.onclose = function() {
        setTimeout(function() {
          location.reload();
        }, 1000);
      };
    }, 1000);
  };
})();
</script>
</body>`;

interface ServeOptions {
  port: number;
  content: string;
  output: string;
  templates: string;
}

function injectReloadScript(html: string): string {
  if (html.includes('</body>')) {
    return html.replace('</body>', RELOAD_SCRIPT);
  }
  return html + RELOAD_SCRIPT.replace('</body>', '');
}

function getContentType(filePath: string): string {
  const ext = path.extname(filePath).toLowerCase();
  const types: Record<string, string> = {
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
  return types[ext] || 'application/octet-stream';
}

function serveFile(
  res: http.ServerResponse,
  filePath: string
): void {
  try {
    const content = fs.readFileSync(filePath);
    const contentType = getContentType(filePath);

    let body = content;
    if (contentType === 'text/html') {
      let html = content.toString('utf-8');
      html = injectReloadScript(html);
      body = Buffer.from(html, 'utf-8');
    }

    res.writeHead(200, {
      'Content-Type': contentType,
      'Cache-Control': 'no-cache, no-store, must-revalidate',
      'Content-Length': String(body.length),
    });
    res.end(body);
  } catch {
    res.writeHead(404, { 'Content-Type': 'text/plain' });
    res.end('Not Found');
  }
}

interface ServerInstance {
  server: http.Server;
  close: () => Promise<void>;
  rebuild: () => void;
}

export function startServer(
  options: ServeOptions
): ServerInstance {
  const { port, content, output, templates } = options;

  const wss = new WebSocketServer({ noServer: true });
  const clients = new Set<WebSocket>();

  wss.on('connection', (ws) => {
    clients.add(ws);
    ws.on('close', () => clients.delete(ws));
  });

  function broadcastReload(): void {
    for (const client of clients) {
      if (client.readyState === WebSocket.OPEN) {
        client.send('reload');
      }
    }
  }

  function rebuild(): void {
    try {
      const pages = parseDirectory(content);
      generateSite(pages, output, templates);
      console.log(`Site rebuilt (${pages.length} pages)`);
      broadcastReload();
    } catch (err) {
      console.error('Build error:', err);
    }
  }

  let rebuildTimer: ReturnType<typeof setTimeout> | null = null;

  const watcher = chokidar.watch([content, templates], {
    ignoreInitial: true,
    usePolling: true,
    interval: 100,
  });

  watcher.on('all', () => {
    if (rebuildTimer) clearTimeout(rebuildTimer);
    rebuildTimer = setTimeout(rebuild, 150);
  });

  const server = http.createServer((req, res) => {
    if (!req.url) {
      res.writeHead(404);
      res.end('Not Found');
      return;
    }

    let urlPath = req.url.split('?')[0];

    if (urlPath === '/') {
      urlPath = '/index.html';
    }

    const resolvedOutput = path.resolve(output);
    const relativePath = urlPath.replace(/^\//, '');
    const resolvedPath = path.resolve(output, relativePath);

    if (!resolvedPath.startsWith(resolvedOutput + path.sep) && resolvedPath !== resolvedOutput) {
      res.writeHead(403, { 'Content-Type': 'text/plain' });
      res.end('Forbidden');
      return;
    }

    serveFile(res, resolvedPath);
  });

  server.on('upgrade', (req, socket, head) => {
    wss.handleUpgrade(req, socket, head, (ws) => {
      wss.emit('connection', ws, req);
    });
  });

  server.listen(port, () => {
    console.log(`Dev server running at http://localhost:${port}`);
    console.log(`Watching ${content}/ and ${templates}/ for changes`);
  });

  const close = async (): Promise<void> => {
    await watcher.close();
    for (const client of clients) {
      client.close();
    }
    wss.close();
    await new Promise<void>((resolve) => server.close(() => resolve()));
  };

  return { server, close, rebuild };
}
