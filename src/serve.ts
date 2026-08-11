import http from 'http';
import fs from 'fs';
import path from 'path';
import { WebSocketServer, WebSocket } from 'ws';
import chokidar from 'chokidar';
import { build } from './build';
import { ServeOptions } from './types';

function getMimeType(filePath: string): string {
  const ext = path.extname(filePath).toLowerCase();
  const mimeTypes: Record<string, string> = {
    '.html': 'text/html',
    '.htm': 'text/html',
    '.css': 'text/css',
    '.js': 'application/javascript',
    '.json': 'application/json',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif': 'image/gif',
    '.svg': 'image/svg+xml',
    '.ico': 'image/x-icon',
  };
  return mimeTypes[ext] || 'application/octet-stream';
}

function injectReloadScript(html: string, port: number): string {
  const script = `<script>(function(){var s=new WebSocket('ws://localhost:${port}/__livereload');s.onmessage=function(m){if(m.data==='reload')window.location.reload()};})();</script>`;
  if (html.includes('</body>')) {
    return html.replace('</body>', script + '</body>');
  }
  return html + script;
}

export function serve(options: ServeOptions): http.Server {
  const { contentDir, outputDir, templatesDir, port } = options;
  const resolvedOutputDir = path.resolve(outputDir);
  const resolvedTemplatesDir = path.resolve(templatesDir || './templates');

  build({ contentDir, outputDir, templatesDir });

  const server = http.createServer((req, res) => {
    const url = req.url || '/';
    const reqPath = url === '/' ? 'index.html' : url;
    const relativePath = reqPath.startsWith('/') ? reqPath.slice(1) : reqPath;
    const filePath = path.join(resolvedOutputDir, relativePath);

    const resolved = path.resolve(filePath);
    if (!resolved.startsWith(resolvedOutputDir + path.sep) && resolved !== resolvedOutputDir) {
      res.writeHead(403);
      res.end('Forbidden');
      return;
    }

    if (!fs.existsSync(resolved) || !fs.statSync(resolved).isFile()) {
      res.writeHead(404);
      res.end('Not Found');
      return;
    }

    const mimeType = getMimeType(resolved);

    if (mimeType === 'text/html') {
      let html = fs.readFileSync(resolved, 'utf-8');
      html = injectReloadScript(html, port);
      res.writeHead(200, { 'Content-Type': mimeType });
      res.end(html);
    } else {
      const content = fs.readFileSync(resolved);
      res.writeHead(200, { 'Content-Type': mimeType });
      res.end(content);
    }
  });

  const wss = new WebSocketServer({ noServer: true });

  server.on('upgrade', (request, socket, head) => {
    const { pathname } = new URL(request.url || '', `http://localhost:${port}`);
    if (pathname === '/__livereload') {
      wss.handleUpgrade(request, socket, head, (ws) => {
        wss.emit('connection', ws, request);
      });
    } else {
      socket.destroy();
    }
  });

  const clients = new Set<WebSocket>();

  wss.on('connection', (ws) => {
    clients.add(ws);
    ws.on('close', () => {
      clients.delete(ws);
    });
  });

  const watchPaths = [
    path.resolve(contentDir),
    resolvedTemplatesDir,
  ];

  let rebuildTimeout: ReturnType<typeof setTimeout> | null = null;

  const watcher = chokidar.watch(watchPaths, {
    ignoreInitial: true,
    awaitWriteFinish: {
      stabilityThreshold: 200,
      pollInterval: 100,
    },
  });

  watcher.on('all', (event, filePath) => {
    console.log(`[change] ${event}: ${filePath}`);
    if (rebuildTimeout) clearTimeout(rebuildTimeout);
    rebuildTimeout = setTimeout(() => {
      try {
        build({ contentDir, outputDir, templatesDir });
        console.log('[rebuilt]');
        for (const client of clients) {
          if (client.readyState === WebSocket.OPEN) {
            client.send('reload');
          }
        }
      } catch (err) {
        console.error('[build error]', (err as Error).message);
      }
    }, 150);
  });

  server.on('close', () => {
    watcher.close();
    wss.close();
  });

  server.listen(port, () => {
    console.log(`Dev server running at http://localhost:${port}/`);
  });

  return server;
}
