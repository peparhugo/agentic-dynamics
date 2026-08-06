import http from 'http';
import { readFileSync, existsSync } from 'fs';
import { join, extname } from 'path';
import { WebSocketServer, WebSocket } from 'ws';
import chokidar from 'chokidar';
import { generate } from './generator';
import { SiteConfig } from './types';

const MIME: Record<string, string> = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css',
  '.js': 'application/javascript',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.svg': 'image/svg+xml',
  '.xml': 'application/xml',
  '.json': 'application/json',
};

export function startDevServer(config: SiteConfig): void {
  const { output, devPort: port } = config;

  const wss = new WebSocketServer({ noServer: true });
  const clients = new Set<WebSocket>();

  wss.on('connection', (ws) => {
    clients.add(ws);
    ws.on('close', () => clients.delete(ws));
  });

  function broadcast() {
    for (const c of clients) {
      c.send('reload');
    }
  }

  const server = http.createServer((req, res) => {
    const urlPath = (req.url || '/index.html').replace(/\?.*$/, '');
    const safePath = urlPath.replace(/^\/+/, '');
    const filePath = join(output, safePath || 'index.html');

    if (existsSync(filePath)) {
      const ext = extname(filePath);
      const contentType = MIME[ext] || 'application/octet-stream';
      try {
        const data = readFileSync(filePath);
        res.writeHead(200, { 'Content-Type': contentType });
        res.end(data);
      } catch {
        res.writeHead(500);
        res.end('Internal Server Error');
      }
    } else {
      // fallback to index.html for SPA-like routing
      const indexPath = join(output, 'index.html');
      if (existsSync(indexPath)) {
        res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
        res.end(readFileSync(indexPath));
      } else {
        res.writeHead(404);
        res.end('Not Found');
      }
    }
  });

  server.on('upgrade', (req, socket, head) => {
    if (req.url === '/__ssg_reload') {
      wss.handleUpgrade(req, socket, head, (ws) => {
        wss.emit('connection', ws, req);
      });
    } else {
      socket.destroy();
    }
  });

  server.listen(port, () => {
    console.log(`Dev server running at http://localhost:${port}`);
    console.log(`Watching ${config.source} and ${config.templates}`);
  });

  const watcher = chokidar.watch([config.source, config.templates], {
    ignoreInitial: true,
    awaitWriteFinish: { stabilityThreshold: 100, pollInterval: 50 },
  });

  const rebuild = () => {
    console.log('Changes detected, rebuilding...');
    try {
      generate(config, { silent: true, isDev: true });
      broadcast();
      console.log('Rebuild complete');
    } catch (err) {
      console.error('Build error:', err);
    }
  };

  watcher.on('add', rebuild);
  watcher.on('change', rebuild);
  watcher.on('unlink', rebuild);

  process.on('SIGINT', () => {
    watcher.close();
    server.close();
    wss.close();
    process.exit(0);
  });
}
