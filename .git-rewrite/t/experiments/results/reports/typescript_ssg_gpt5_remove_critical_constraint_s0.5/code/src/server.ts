import http from 'node:http';
import path from 'node:path';
import fs from 'node:fs';
import chokidar from 'chokidar';
import { WebSocketServer } from 'ws';
import { buildSite } from './builder';
import { BuildOptions } from './types';

function serveStatic(req: http.IncomingMessage, res: http.ServerResponse, outDir: string) {
  const url = (req.url || '/').split('?')[0];
  const safePath = path.normalize(decodeURIComponent(url)).replace(/^\/+/, '');
  let filePath = path.join(outDir, safePath);
  try {
    const stat = fs.existsSync(filePath) ? fs.statSync(filePath) : null;
    if (stat && stat.isDirectory()) {
      filePath = path.join(filePath, 'index.html');
    }
    if (!fs.existsSync(filePath)) {
      res.statusCode = 404;
      res.end('Not Found');
      return;
    }
    const ext = path.extname(filePath).toLowerCase();
    const type = ext === '.html' ? 'text/html; charset=utf-8' : ext === '.css' ? 'text/css' : ext === '.js' ? 'text/javascript' : ext === '.xml' ? 'application/xml' : 'application/octet-stream';
    res.setHeader('Content-Type', type);
    fs.createReadStream(filePath).pipe(res);
  } catch (e) {
    res.statusCode = 500;
    res.end('Server Error');
  }
}

export async function startDevServer(opts: BuildOptions & { port?: number; watch?: boolean }) {
  const port = opts.devServerPort || opts.port || 5173;
  const outDir = opts.outDir;

  // Initial build with live reload injection
  await buildSite({ ...opts, devServerPort: port });

  const server = http.createServer((req, res) => serveStatic(req, res, outDir));
  const wss = new WebSocketServer({ server, path: '/livereload' });

  function broadcastReload() {
    for (const client of wss.clients) {
      try {
        client.send('reload');
      } catch {}
    }
  }

  if (opts.watch !== false) {
    const watcher = chokidar.watch([opts.srcDir, opts.templatesDir], { ignoreInitial: true });
    watcher.on('all', async () => {
      try {
        await buildSite({ ...opts, devServerPort: port });
        broadcastReload();
      } catch (e) {
        console.error('Build error:', e);
      }
    });
  }

  await new Promise<void>((resolve) => server.listen(port, resolve));
  return { port, close: () => server.close() };
}
