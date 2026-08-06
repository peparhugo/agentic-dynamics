import http from 'http';
import { readFile } from 'fs/promises';
import { existsSync } from 'fs';
import { join, extname } from 'path';
import { WebSocketServer, WebSocket } from 'ws';
import chokidar from 'chokidar';
import { build } from './generator.js';
import { ServeOptions } from './types.js';

const LIVE_RELOAD_SCRIPT = `
<script>
(function() {
  var protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  var ws = new WebSocket(protocol + '//' + location.host);
  ws.onmessage = function(msg) {
    if (msg.data === 'reload') location.reload();
  };
  ws.onclose = function() {
    console.log('Live reload disconnected, retrying in 1s...');
    setTimeout(function() { location.reload(); }, 1000);
  };
})();
</script>
`;

function injectReloadScript(html: string): string {
  if (html.includes('</body>')) {
    return html.replace('</body>', `${LIVE_RELOAD_SCRIPT}</body>`);
  }
  return html + LIVE_RELOAD_SCRIPT;
}

const MIME_TYPES: Record<string, string> = {
  '.html': 'text/html',
  '.css': 'text/css',
  '.js': 'application/javascript',
  '.json': 'application/json',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.svg': 'image/svg+xml',
  '.xml': 'application/xml',
  '.ico': 'image/x-icon',
};

export async function serve(options: ServeOptions): Promise<void> {
  await build(options);

  const wss = new WebSocketServer({ noServer: true });

  const server = http.createServer(async (req, res) => {
    const url = new URL(req.url || '/', `http://localhost:${options.port}`);
    let filePath = join(options.output, url.pathname);

    if (url.pathname.endsWith('/')) {
      filePath = join(filePath, 'index.html');
    }

    if (!existsSync(filePath)) {
      res.writeHead(404, { 'Content-Type': 'text/plain' });
      res.end('Not found');
      return;
    }

    try {
      const content = await readFile(filePath);
      const ext = extname(filePath);
      const contentType = MIME_TYPES[ext] || 'application/octet-stream';

      let body = content;
      if (contentType === 'text/html') {
        body = Buffer.from(injectReloadScript(content.toString('utf-8')));
      }

      res.writeHead(200, { 'Content-Type': contentType });
      res.end(body);
    } catch {
      res.writeHead(500, { 'Content-Type': 'text/plain' });
      res.end('Internal server error');
    }
  });

  server.on('upgrade', (req, socket, head) => {
    wss.handleUpgrade(req, socket, head, (ws) => {
      wss.emit('connection', ws, req);
    });
  });

  let rebuildTimer: ReturnType<typeof setTimeout> | null = null;

  const debouncedRebuild = () => {
    if (rebuildTimer) clearTimeout(rebuildTimer);
    rebuildTimer = setTimeout(async () => {
      try {
        await build(options);
        for (const client of wss.clients) {
          if (client.readyState === WebSocket.OPEN) {
            client.send('reload');
          }
        }
      } catch (err) {
        console.error('Rebuild failed:', err);
      }
    }, 300);
  };

  const watcher = chokidar.watch([options.source, options.templates], {
    ignoreInitial: true,
  });

  watcher.on('change', debouncedRebuild);
  watcher.on('add', debouncedRebuild);
  watcher.on('unlink', debouncedRebuild);

  const port = parseInt(options.port, 10) || 3000;
  server.listen(port, () => {
    console.log(`Dev server running at http://localhost:${port}/`);
  });

  const shutdown = () => {
    watcher.close();
    wss.close();
    server.close();
    process.exit(0);
  };

  process.on('SIGINT', shutdown);
  process.on('SIGTERM', shutdown);
}
