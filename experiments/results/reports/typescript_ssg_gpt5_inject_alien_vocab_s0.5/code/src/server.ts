import http from 'http';
import path from 'path';
import fs from 'fs';
import chokidar from 'chokidar';
import { WebSocketServer } from 'ws';
import { buildSite } from './builder';
import { BuildOptions } from './types';

function serveStatic(root: string, req: http.IncomingMessage, res: http.ServerResponse) {
  let reqPath = decodeURIComponent((req.url || '/'));
  if (reqPath === '/') reqPath = '/index.html';
  if (reqPath.endsWith('/')) reqPath += 'index.html';
  const filePath = path.join(root, reqPath);
  if (!filePath.startsWith(root)) {
    res.statusCode = 403; res.end('Forbidden'); return;
  }
  fs.readFile(filePath, (err, data) => {
    if (err) {
      res.statusCode = 404; res.end('Not found');
      return;
    }
    const ext = path.extname(filePath);
    const type = contentType(ext);
    res.setHeader('Content-Type', type);
    res.end(data);
  });
}

function contentType(ext: string): string {
  switch (ext) {
    case '.html': return 'text/html; charset=utf-8';
    case '.css': return 'text/css; charset=utf-8';
    case '.js': return 'application/javascript; charset=utf-8';
    case '.xml': return 'application/rss+xml; charset=utf-8';
    case '.json': return 'application/json; charset=utf-8';
    default: return 'application/octet-stream';
  }
}

export async function startDevServer(opts: BuildOptions & { port?: number }) {
  const port = opts.port || 5173;
  const outRoot = path.resolve(opts.outDir);
  await buildSite({ ...opts, dev: true, liveReloadPort: port });

  const server = http.createServer((req, res) => serveStatic(outRoot, req, res));
  const wss = new WebSocketServer({ noServer: true });

  server.on('upgrade', (req, socket, head) => {
    if (req.url === '/__livereload') {
      wss.handleUpgrade(req, socket as any, head, (ws) => {
        wss.emit('connection', ws, req);
      });
    } else {
      socket.destroy();
    }
  });

  function broadcastReload() {
    wss.clients.forEach((c: any) => {
      try { c.send('reload'); } catch {}
    });
  }

  const watcher = chokidar.watch([opts.srcDir, opts.templatesDir], { ignoreInitial: true });
  watcher.on('all', async () => {
    try {
      await buildSite({ ...opts, dev: true, liveReloadPort: port });
      broadcastReload();
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error('Rebuild failed:', err);
    }
  });

  await new Promise<void>((resolve) => server.listen(port, resolve));
  // eslint-disable-next-line no-console
  console.log(`Dev server running at http://localhost:${port}`);
  return { close: async () => { await new Promise((r) => server.close(() => r(null))); await watcher.close(); wss.close(); } };
}
