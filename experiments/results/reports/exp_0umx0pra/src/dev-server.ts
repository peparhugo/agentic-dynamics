import http from 'http';
import fs from 'fs';
import path from 'path';
import { WebSocketServer, WebSocket } from 'ws';
import chokidar from 'chokidar';
import { SiteConfig } from './types';
import { generateSite } from './generator';

const RELOAD_WS_PATH = '/__reload';

const RELOAD_SCRIPT_INJECT = `
<script>
(function() {
  var ws = new WebSocket('ws://' + location.host + '${RELOAD_WS_PATH}');
  ws.onmessage = function(msg) {
    if (msg.data === 'reload') {
      location.reload();
    }
  };
  ws.onclose = function() {
    console.log('Live reload disconnected, retrying...');
    setTimeout(function() {
      window.location.reload();
    }, 2000);
  };
})();
</script>`;

function getMimeType(filePath: string): string {
  const ext = path.extname(filePath).toLowerCase();
  const mimes: Record<string, string> = {
    '.html': 'text/html',
    '.css': 'text/css',
    '.js': 'application/javascript',
    '.json': 'application/json',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.svg': 'image/svg+xml',
    '.xml': 'application/xml',
    '.txt': 'text/plain',
  };
  return mimes[ext] || 'application/octet-stream';
}

export async function startDevServer(config: SiteConfig): Promise<void> {
  await generateSite(config);

  injectReloadScript(config);

  const clients = new Set<WebSocket>();

  const server = http.createServer((req, res) => {
    const url = req.url || '/';
    let filePath = path.join(config.outputDir, url === '/' ? 'index.html' : url);

    if (fs.existsSync(filePath) && fs.statSync(filePath).isFile()) {
      res.writeHead(200, { 'Content-Type': getMimeType(filePath) });
      res.end(fs.readFileSync(filePath));
      return;
    }

    const indexPath = path.join(filePath, 'index.html');
    if (fs.existsSync(indexPath)) {
      res.writeHead(200, { 'Content-Type': 'text/html' });
      res.end(fs.readFileSync(indexPath));
      return;
    }

    res.writeHead(404);
    res.end('Not found');
  });

  const wss = new WebSocketServer({ noServer: true });

  server.on('upgrade', (request, socket, head) => {
    if (request.url === RELOAD_WS_PATH) {
      wss.handleUpgrade(request, socket, head, (ws) => {
        wss.emit('connection', ws, request);
      });
    } else {
      socket.destroy();
    }
  });

  wss.on('connection', (ws) => {
    clients.add(ws);
    ws.on('close', () => clients.delete(ws));
  });

  const reloadClients = () => {
    for (const client of clients) {
      if (client.readyState === WebSocket.OPEN) {
        client.send('reload');
      }
    }
  };

  const watcher = chokidar.watch([config.sourceDir, config.templateDir], {
    ignoreInitial: true,
  });

  let rebuildTimeout: NodeJS.Timeout | null = null;
  watcher.on('all', async (event, filePath) => {
    if (rebuildTimeout) clearTimeout(rebuildTimeout);
    rebuildTimeout = setTimeout(async () => {
      try {
        await generateSite(config);
        injectReloadScript(config);
        reloadClients();
        console.log(`[${new Date().toISOString()}] Rebuilt after ${event}: ${filePath}`);
      } catch (err) {
        console.error('Rebuild error:', err);
      }
    }, 100);
  });

  server.listen(config.port, () => {
    console.log(`Dev server running at http://localhost:${config.port}`);
  });
}

function injectReloadScript(config: SiteConfig): void {
  function walk(dir: string) {
    if (!fs.existsSync(dir)) return;
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const fullPath = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        walk(fullPath);
      } else if (entry.name.endsWith('.html')) {
        let html = fs.readFileSync(fullPath, 'utf-8');
        if (!html.includes(RELOAD_WS_PATH)) {
          html = html.replace('</body>', RELOAD_SCRIPT_INJECT + '</body>');
          fs.writeFileSync(fullPath, html);
        }
      }
    }
  }
  walk(config.outputDir);
}
