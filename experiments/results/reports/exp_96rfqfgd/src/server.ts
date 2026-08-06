import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { join, extname } from 'node:path';
import { WebSocketServer, WebSocket } from 'ws';
import { watch } from 'chokidar';
import type { SiteConfig } from './types.js';

const RELOAD_SCRIPT = `
<script>
  (function() {
    var ws = new WebSocket('ws://' + location.host + '/__reload');
    ws.onmessage = function(msg) {
      if (msg.data === 'reload') location.reload();
    };
    ws.onclose = function() {
      setTimeout(function() { location.reload(); }, 2000);
    };
  })();
</script>
</body>`;

const MIME_TYPES: Record<string, string> = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css',
  '.js': 'application/javascript',
  '.json': 'application/json',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.svg': 'image/svg+xml',
  '.xml': 'application/xml',
  '.ico': 'image/x-icon',
};

export async function startDevServer(
  config: SiteConfig,
  port: number,
  buildFn: () => Promise<void>,
): Promise<void> {
  const server = createServer(async (req, res) => {
    const url = new URL(req.url || '/', `http://localhost:${port}`);
    const filePath = join(
      config.outputDir,
      url.pathname === '/' ? 'index.html' : url.pathname,
    );

    try {
      let content = await readFile(filePath);
      const ext = extname(filePath);
      const contentType = MIME_TYPES[ext] || 'application/octet-stream';

      if (ext === '.html' || ext === '.htm') {
        const html = content.toString('utf-8');
        if (!html.includes('/__reload')) {
          const injected = html.replace('</body>', RELOAD_SCRIPT);
          content = Buffer.from(injected, 'utf-8');
        }
      }

      res.writeHead(200, { 'Content-Type': contentType });
      res.end(content);
    } catch {
      if (url.pathname === '/__reload') {
        res.writeHead(200);
        res.end();
        return;
      }
      res.writeHead(404);
      res.end('Not Found');
    }
  });

  const wss = new WebSocketServer({ server, path: '/__reload' });

  const clients = new Set<WebSocket>();
  wss.on('connection', (ws) => {
    clients.add(ws);
    ws.on('close', () => clients.delete(ws));
  });

  server.listen(port, () => {
    console.log(`Dev server running at http://localhost:${port}`);
  });

  const watcher = watch([config.sourceDir, config.templateDir], {
    ignoreInitial: true,
  });

  const rebuild = async (event: string, path: string) => {
    console.log(`[${event}] ${path}`);
    try {
      await buildFn();
      for (const client of clients) {
        if (client.readyState === WebSocket.OPEN) {
          client.send('reload');
        }
      }
    } catch (err) {
      console.error('Build error:', err);
    }
  };

  watcher.on('add', (p) => rebuild('add', p));
  watcher.on('change', (p) => rebuild('change', p));
  watcher.on('unlink', (p) => rebuild('unlink', p));

  process.on('SIGINT', () => {
    watcher.close();
    wss.close();
    server.close();
    process.exit(0);
  });
}
