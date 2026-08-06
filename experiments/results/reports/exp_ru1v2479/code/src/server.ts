import { createServer, IncomingMessage, ServerResponse } from 'node:http';
import { readFileSync, existsSync, statSync } from 'node:fs';
import { join, extname } from 'node:path';
import chokidar from 'chokidar';
import { WebSocketServer, WebSocket } from 'ws';
import { SiteConfig } from './types';
import { generate } from './generator';

const MIME: Record<string, string> = {
  '.html': 'text/html',
  '.css': 'text/css',
  '.js': 'application/javascript',
  '.json': 'application/json',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.xml': 'application/xml',
};

function serveFile(res: ServerResponse, path: string): void {
  try {
    const data = readFileSync(path);
    const ext = extname(path);
    res.writeHead(200, { 'Content-Type': MIME[ext] || 'text/plain' });
    res.end(data);
  } catch {
    res.writeHead(404);
    res.end('Not Found');
  }
}

export function startServer(config: SiteConfig): void {
  const wss = new WebSocketServer({ port: config.port + 1 });
  const clients = new Set<WebSocket>();

  wss.on('connection', (ws) => {
    clients.add(ws);
    ws.on('close', () => clients.delete(ws));
  });

  function notifyClients(): void {
    for (const client of clients) {
      if (client.readyState === WebSocket.OPEN) {
        client.send('reload');
      }
    }
  }

  const server = createServer((req: IncomingMessage, res: ServerResponse) => {
    const url = req.url || '/';
    let filePath = join(config.outputDir, url === '/' ? 'index.html' : url);

    if (!existsSync(filePath)) {
      filePath = join(config.outputDir, url, 'index.html');
    }
    if (!existsSync(filePath)) {
      filePath = join(config.outputDir, 'index.html');
    }

    serveFile(res, filePath);
  });

  let debounceTimer: ReturnType<typeof setTimeout> | null = null;
  function scheduleRebuild(): void {
    if (debounceTimer) clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      try {
        generate(config, true);
        notifyClients();
        console.log('[staticsite] rebuilt');
      } catch (err) {
        console.error('[staticsite] build error:', err);
      }
    }, 200);
  }

  const watcher = chokidar.watch(
    [config.sourceDir, config.templateDir],
    { ignoreInitial: true },
  );
  watcher.on('all', scheduleRebuild);

  server.listen(config.port, () => {
    generate(config, true);
    console.log(`[staticsite] dev server at http://localhost:${config.port}`);
  });

  process.on('SIGINT', () => {
    watcher.close();
    wss.close();
    server.close();
    process.exit(0);
  });
}
