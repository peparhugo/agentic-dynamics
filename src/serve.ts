import http from 'http';
import fs from 'fs';
import path from 'path';
import { WebSocketServer, WebSocket } from 'ws';
import chokidar from 'chokidar';
import { build, BuildOptions } from './build';

const LIVE_RELOAD_SCRIPT = '<script>(function(){var s=new WebSocket(\'ws://\'+location.host+\'/__ssg_livereload\');s.onmessage=function(e){if(e.data===\'reload\')location.reload();};})();</script>';

const MIME_TYPES: Record<string, string> = {
  '.html': 'text/html',
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

function getMimeType(filePath: string): string {
  const ext = path.extname(filePath).toLowerCase();
  return MIME_TYPES[ext] || 'application/octet-stream';
}

export interface ServeOptions {
  contentDir: string;
  outputDir: string;
  templatesDir?: string;
  port: number;
}

export interface ServerInstance {
  server: http.Server;
  ready: Promise<void>;
  close(): Promise<void>;
}

export function serve(options: ServeOptions): ServerInstance {
  const contentDir = path.resolve(options.contentDir);
  const outputDir = path.resolve(options.outputDir);
  const { templatesDir, port } = options;

  const buildOpts: BuildOptions = { contentDir, outputDir, templatesDir };
  build(buildOpts);

  const wss = new WebSocketServer({ noServer: true });

  const server = http.createServer((req, res) => {
    try {
      if (!req.url) {
        res.writeHead(404);
        res.end();
        return;
      }

      const urlPath = req.url.split('?')[0];

      let filePath: string;
      if (urlPath === '/') {
        filePath = path.join(outputDir, 'index.html');
      } else {
        filePath = path.join(outputDir, urlPath);
        if (fs.existsSync(filePath) && fs.statSync(filePath).isDirectory()) {
          filePath = path.join(filePath, 'index.html');
        }
      }

      filePath = path.resolve(filePath);

      if (!filePath.startsWith(outputDir + path.sep) && filePath !== path.join(outputDir, 'index.html')) {
        res.writeHead(403);
        res.end();
        return;
      }

      if (!fs.existsSync(filePath) || !fs.statSync(filePath).isFile()) {
        res.writeHead(404);
        res.end('Not Found');
        return;
      }

      const ext = path.extname(filePath).toLowerCase();
      const mimeType = getMimeType(filePath);

      let content = fs.readFileSync(filePath);

      if (ext === '.html') {
        const html = content.toString('utf-8');
        const injectedHtml = html.replace('</body>', LIVE_RELOAD_SCRIPT + '</body>');
        content = Buffer.from(injectedHtml, 'utf-8');
      }

      res.writeHead(200, { 'Content-Type': mimeType });
      res.end(content);
    } catch {
      res.writeHead(500);
      res.end('Internal Server Error');
    }
  });

  server.on('upgrade', (request, socket, head) => {
    if (request.url === '/__ssg_livereload') {
      wss.handleUpgrade(request, socket, head, (ws) => {
        wss.emit('connection', ws, request);
      });
    } else {
      socket.destroy();
    }
  });

  let rebuildTimeout: NodeJS.Timeout | null = null;
  const clients: Set<WebSocket> = new Set();

  wss.on('connection', (ws) => {
    clients.add(ws);
    ws.on('close', () => {
      clients.delete(ws);
    });
  });

  function triggerRebuild() {
    if (rebuildTimeout) {
      clearTimeout(rebuildTimeout);
    }
    rebuildTimeout = setTimeout(() => {
      try {
        build(buildOpts);
        for (const client of clients) {
          if (client.readyState === WebSocket.OPEN) {
            client.send('reload');
          }
        }
      } catch {
        // Silently handle build errors during watch
      }
    }, 300);
  }

  const watchDirs: string[] = [contentDir];
  if (templatesDir) {
    watchDirs.push(path.resolve(templatesDir));
  }

  const watcher = chokidar.watch(watchDirs, {
    ignoreInitial: true,
    usePolling: true,
    interval: 200,
  });

  watcher.on('all', () => {
    triggerRebuild();
  });

  const ready = new Promise<void>((resolve) => {
    let watcherReady = false;
    let serverReady = false;
    const check = () => {
      if (watcherReady && serverReady) resolve();
    };
    watcher.on('ready', () => {
      watcherReady = true;
      check();
    });
    server.once('listening', () => {
      serverReady = true;
      check();
    });
  });

  server.listen(port);

  return {
    server,
    ready,
    close(): Promise<void> {
      return new Promise((resolve) => {
        watcher.close();
        wss.close(() => {
          for (const client of clients) {
            client.terminate();
          }
          clients.clear();
          server.close(() => resolve());
        });
      });
    },
  };
}
