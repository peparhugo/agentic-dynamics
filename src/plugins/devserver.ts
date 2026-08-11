import http from 'http';
import fs from 'fs';
import path from 'path';
import chokidar from 'chokidar';
import { WebSocketServer, WebSocket } from 'ws';
import { Plugin, PluginContext } from '../plugin';

const RELOAD_SCRIPT = `
<script>
(function() {
  var ws = new WebSocket('ws://' + location.host);
  ws.onmessage = function(msg) {
    if (msg.data === 'reload') location.reload();
  };
  ws.onclose = function() {
    setTimeout(function() {
      var ws2 = new WebSocket('ws://' + location.host);
      ws2.onmessage = function(msg) {
        if (msg.data === 'reload') location.reload();
      };
      ws2.onclose = function() {
        setTimeout(function() {
          location.reload();
        }, 1000);
      };
    }, 1000);
  };
})();
</script>
</body>`;

function injectReloadScript(html: string): string {
  if (html.includes('</body>')) {
    return html.replace('</body>', RELOAD_SCRIPT);
  }
  return html + RELOAD_SCRIPT.replace('</body>', '');
}

function getContentType(filePath: string): string {
  const ext = path.extname(filePath).toLowerCase();
  const types: Record<string, string> = {
    '.html': 'text/html',
    '.css': 'text/css',
    '.js': 'application/javascript',
    '.json': 'application/json',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.gif': 'image/gif',
    '.svg': 'image/svg+xml',
    '.ico': 'image/x-icon',
  };
  return types[ext] || 'application/octet-stream';
}

function serveFile(
  res: http.ServerResponse,
  filePath: string
): void {
  try {
    const content = fs.readFileSync(filePath);
    const contentType = getContentType(filePath);

    let body = content;
    if (contentType === 'text/html') {
      let html = content.toString('utf-8');
      html = injectReloadScript(html);
      body = Buffer.from(html, 'utf-8');
    }

    res.writeHead(200, {
      'Content-Type': contentType,
      'Cache-Control': 'no-cache, no-store, must-revalidate',
      'Content-Length': String(body.length),
    });
    res.end(body);
  } catch {
    res.writeHead(404, { 'Content-Type': 'text/plain' });
    res.end('Not Found');
  }
}

export interface ServerInstance {
  server: http.Server;
  close: () => Promise<void>;
  rebuild: () => void;
}

export class DevServerPlugin implements Plugin {
  name = 'devserver';

  private wss: WebSocketServer | null = null;
  private clients: Set<WebSocket> = new Set();
  private watcher: chokidar.FSWatcher | null = null;
  private rebuildTimer: ReturnType<typeof setTimeout> | null = null;
  private server: http.Server | null = null;
  private rebuildCallback: (() => Promise<void>) | null = null;

  onEnd(_context: PluginContext): void {
    this.cleanup();
  }

  async startServer(
    context: PluginContext,
    rebuildFn: () => Promise<void>
  ): Promise<ServerInstance> {
    this.rebuildCallback = rebuildFn;
    const { port, content, output, templates } = context.options;

    this.wss = new WebSocketServer({ noServer: true });

    this.wss.on('connection', (ws) => {
      this.clients.add(ws);
      ws.on('close', () => this.clients.delete(ws));
    });

    this.watcher = chokidar.watch([content, templates], {
      ignoreInitial: true,
      usePolling: true,
      interval: 100,
    });

    this.watcher.on('all', () => {
      if (this.rebuildTimer) clearTimeout(this.rebuildTimer);
      this.rebuildTimer = setTimeout(() => this.rebuild(), 150);
    });

    this.server = http.createServer((req, res) => {
      if (!req.url) {
        res.writeHead(404);
        res.end('Not Found');
        return;
      }

      let urlPath = req.url.split('?')[0];

      if (urlPath === '/') {
        urlPath = '/index.html';
      }

      const resolvedOutput = path.resolve(output);
      const relativePath = urlPath.replace(/^\//, '');
      const resolvedPath = path.resolve(output, relativePath);

      if (!resolvedPath.startsWith(resolvedOutput + path.sep) && resolvedPath !== resolvedOutput) {
        res.writeHead(403, { 'Content-Type': 'text/plain' });
        res.end('Forbidden');
        return;
      }

      serveFile(res, resolvedPath);
    });

    this.server.on('upgrade', (req, socket, head) => {
      if (this.wss) {
        this.wss.handleUpgrade(req, socket, head, (ws) => {
          this.wss!.emit('connection', ws, req);
        });
      }
    });

    await new Promise<void>((resolve) => {
      this.server!.listen(port, () => {
        console.log(`Dev server running at http://localhost:${(this.server!.address() as { port: number }).port}`);
        console.log(`Watching ${content}/ and ${templates}/ for changes`);
        resolve();
      });
    });

    const close = async (): Promise<void> => {
      this.cleanup();
    };

    return {
      server: this.server!,
      close,
      rebuild: () => this.rebuild(),
    };
  }

  private async rebuild(): Promise<void> {
    try {
      if (this.rebuildCallback) {
        await this.rebuildCallback();
      }
      this.broadcastReload();
    } catch (err) {
      console.error('Build error:', err);
    }
  }

  private broadcastReload(): void {
    for (const client of this.clients) {
      if (client.readyState === WebSocket.OPEN) {
        client.send('reload');
      }
    }
  }

  private cleanup(): void {
    if (this.watcher) {
      this.watcher.close();
      this.watcher = null;
    }
    for (const client of this.clients) {
      client.close();
    }
    this.clients.clear();
    if (this.wss) {
      this.wss.close();
      this.wss = null;
    }
    if (this.server) {
      this.server.close();
      this.server = null;
    }
  }
}
