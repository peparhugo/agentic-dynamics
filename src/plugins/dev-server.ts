import http from 'http';
import fs from 'fs';
import path from 'path';
import { WebSocketServer, WebSocket } from 'ws';
import chokidar from 'chokidar';
import { Plugin, BuildContext } from '../plugin';
import { SsgEngine } from '../ssg-engine';

const RELOAD_SCRIPT = `<script>
(function() {
  var ws = new WebSocket('ws://' + location.host);
  ws.onmessage = function(msg) {
    if (msg.data === 'reload') {
      ws.close();
      location.reload();
    }
  };
  ws.onclose = function() {
    console.log('[ssg] Live-reload disconnected. Attempting reconnect in 1s...');
    setTimeout(function() {
      location.reload();
    }, 1000);
  };
})();
</script>`;

function injectReloadScript(html: string): string {
  if (html.includes('</body>')) {
    return html.replace('</body>', RELOAD_SCRIPT + '\n</body>');
  }
  return html + RELOAD_SCRIPT;
}

function getContentType(filePath: string): string {
  const ext = path.extname(filePath).toLowerCase();
  const types: Record<string, string> = {
    '.html': 'text/html; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.js': 'application/javascript; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif': 'image/gif',
    '.svg': 'image/svg+xml',
    '.ico': 'image/x-icon',
  };
  return types[ext] || 'application/octet-stream';
}

function serveFile(res: http.ServerResponse, filePath: string, injectWs: boolean): void {
  try {
    const content = fs.readFileSync(filePath);
    const contentType = getContentType(filePath);

    if (injectWs && contentType.startsWith('text/html')) {
      const html = injectReloadScript(content.toString('utf-8'));
      res.writeHead(200, {
        'Content-Type': 'text/html; charset=utf-8',
        'Content-Length': Buffer.byteLength(html),
      });
      res.end(html);
      return;
    }

    res.writeHead(200, {
      'Content-Type': contentType,
      'Content-Length': content.length,
    });
    res.end(content);
  } catch {
    res.writeHead(404, { 'Content-Type': 'text/plain' });
    res.end('Not Found');
  }
}

export interface DevServerOptions {
  contentDir: string;
  outputDir: string;
  templatesDir: string;
  port: number;
}

export class DevServerPlugin implements Plugin {
  name = 'dev-server';

  private engine: SsgEngine;

  constructor(engine: SsgEngine) {
    this.engine = engine;
  }

  async serve(options: DevServerOptions): Promise<http.Server> {
    const clients = new Set<WebSocket>();

    await this.engine.build({
      contentDir: options.contentDir,
      outputDir: options.outputDir,
      templatesDir: options.templatesDir,
    });

    const server = http.createServer((req, res) => {
      const url = req.url || '/';
      const filePath = url === '/' || url.endsWith('/')
        ? path.join(options.outputDir, 'index.html')
        : path.join(options.outputDir, url);

      if (fs.existsSync(filePath) && fs.statSync(filePath).isFile()) {
        serveFile(res, filePath, true);
      } else {
        const indexPath = path.join(options.outputDir, 'index.html');
        if (fs.existsSync(indexPath)) {
          serveFile(res, indexPath, true);
        } else {
          res.writeHead(404, { 'Content-Type': 'text/plain' });
          res.end('Not Found');
        }
      }
    });

    const wss = new WebSocketServer({ server });

    wss.on('connection', (ws) => {
      clients.add(ws);
      ws.on('close', () => {
        clients.delete(ws);
      });
    });

    function notifyClients(): void {
      const msg = 'reload';
      for (const client of clients) {
        if (client.readyState === WebSocket.OPEN) {
          client.send(msg);
        }
      }
    }

    let rebuildTimer: NodeJS.Timeout | null = null;

    const scheduleRebuild = () => {
      if (rebuildTimer) clearTimeout(rebuildTimer);
      rebuildTimer = setTimeout(async () => {
        try {
          await this.engine.build({
            contentDir: options.contentDir,
            outputDir: options.outputDir,
            templatesDir: options.templatesDir,
          });
          notifyClients();
        } catch (err: unknown) {
          const message = err instanceof Error ? err.message : String(err);
          console.error(`[ssg] Build error: ${message}`);
        }
      }, 150);
    };

    const watcher = chokidar.watch([
      options.contentDir,
      options.templatesDir,
    ], {
      ignoreInitial: true,
      persistent: true,
      usePolling: true,
      interval: 100,
    });

    watcher.on('add', scheduleRebuild);
    watcher.on('change', scheduleRebuild);
    watcher.on('unlink', scheduleRebuild);

    server.on('close', () => {
      watcher.close();
      wss.close();
    });

    server.listen(options.port, () => {
      console.log(`[ssg] Dev server running at http://localhost:${options.port}`);
      console.log(`[ssg] Watching ${options.contentDir}/ and ${options.templatesDir}/ for changes`);
    });

    return server;
  }
}
