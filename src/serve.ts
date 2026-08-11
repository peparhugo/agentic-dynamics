import http from 'http';
import fs from 'fs';
import path from 'path';
import { WebSocketServer, WebSocket } from 'ws';
import chokidar, { FSWatcher } from 'chokidar';
import { build } from './ssg';

export interface ServeOptions {
  contentDir: string;
  outputDir: string;
  templateDir?: string;
  port: number;
}

export interface ServeInstance {
  server: http.Server;
  watcher: FSWatcher;
  wss: WebSocketServer;
}

const LIVE_RELOAD_SCRIPT = `<script>(function(){var w=new WebSocket('ws://'+location.host);w.onmessage=function(e){if(e.data==='reload')location.reload()}})();</script>`;

const MIME_TYPES: Record<string, string> = {
  '.html': 'text/html',
  '.css': 'text/css',
  '.js': 'text/javascript',
  '.json': 'application/json',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.svg': 'image/svg+xml',
};

function injectLiveReload(html: string): string {
  if (html.includes('</body>')) {
    return html.replace('</body>', LIVE_RELOAD_SCRIPT + '</body>');
  }
  return html + LIVE_RELOAD_SCRIPT;
}

export function serve(options: ServeOptions): ServeInstance {
  const { contentDir, outputDir, templateDir, port } = options;

  build({ contentDir, outputDir, templateDir });

  const server = http.createServer((req, res) => {
    const url = req.url === '/' ? '/index.html' : req.url || '/';
    const filePath = path.join(outputDir, url);

    if (fs.existsSync(filePath) && fs.statSync(filePath).isFile()) {
      const ext = path.extname(filePath);
      const contentType = MIME_TYPES[ext] || 'application/octet-stream';

      let content = fs.readFileSync(filePath, 'utf-8');

      if (ext === '.html') {
        content = injectLiveReload(content);
      }

      res.writeHead(200, { 'Content-Type': contentType });
      res.end(content);
    } else {
      res.writeHead(404);
      res.end('Not found');
    }
  });

  const wss = new WebSocketServer({ server });

  const clients = new Set<WebSocket>();

  wss.on('connection', (ws) => {
    clients.add(ws);
    ws.on('close', () => clients.delete(ws));
  });

  function notifyClients() {
    for (const client of clients) {
      if (client.readyState === WebSocket.OPEN) {
        client.send('reload');
      }
    }
  }

  const watchDirs: string[] = [];
  if (fs.existsSync(contentDir)) {
    watchDirs.push(contentDir);
  }
  if (templateDir && fs.existsSync(templateDir)) {
    watchDirs.push(templateDir);
  }

  const watcher = chokidar.watch(watchDirs, {
    ignoreInitial: true,
    awaitWriteFinish: { stabilityThreshold: 100, pollInterval: 50 },
  });

  function rebuild() {
    try {
      build({ contentDir, outputDir, templateDir });
      notifyClients();
    } catch (err) {
      // nop
    }
  }

  watcher.on('change', rebuild);
  watcher.on('add', rebuild);
  watcher.on('unlink', rebuild);

  server.listen(port, () => {
    console.log(`Dev server running at http://localhost:${port}`);
  });

  return { server, watcher, wss };
}
