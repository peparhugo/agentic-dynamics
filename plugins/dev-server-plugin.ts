import * as http from 'http';
import * as fs from 'fs';
import * as path from 'path';
import { WebSocketServer, WebSocket } from 'ws';
import * as chokidar from 'chokidar';
import { Page } from '../src/types';
import { Plugin, BuildContext } from '../src/plugin';
import { build } from '../src/build';

function getReloadScript(): string {
  return `<script>
(function() {
  var ws = new WebSocket('ws://' + location.host);
  ws.onmessage = function(msg) {
    if (msg.data === 'reload') {
      location.reload();
    }
  };
})();
</script>`;
}

export function injectReloadScript(html: string): string {
  const script = getReloadScript();
  if (html.includes('</body>')) {
    return html.replace('</body>', script + '</body>');
  }
  if (html.includes('</html>')) {
    return html.replace('</html>', script + '</html>');
  }
  return html + script;
}

export class DevServerPlugin implements Plugin {
  name = 'dev-server';

  private context: BuildContext | null = null;
  private server: http.Server | null = null;
  private wss: WebSocketServer | null = null;
  private watcher: ReturnType<typeof chokidar.watch> | null = null;
  private connectedClients: Set<WebSocket> = new Set();

  setContext(context: BuildContext): void {
    this.context = context;
  }

  onStart(): void {
    const ctx = this.context;
    if (!ctx) return;

    const contentDir = ctx.contentDir;
    const outputDir = ctx.outputDir;
    const templatesDir = ctx.templatesDir || './templates';

    this.watcher = chokidar.watch([contentDir, templatesDir], {
      ignoreInitial: true,
    });

    this.wss = new WebSocketServer({ noServer: true });

    const mimeTypes: Record<string, string> = {
      '.html': 'text/html',
      '.css': 'text/css',
      '.js': 'application/javascript',
      '.json': 'application/json',
      '.png': 'image/png',
      '.jpg': 'image/jpeg',
      '.svg': 'image/svg+xml',
    };

    this.server = http.createServer((req, res) => {
      const url = req.url || '/';
      const filePath = url === '/' ? '/index.html' : url;
      const fullPath = path.join(path.resolve(outputDir), filePath);

      if (!fs.existsSync(fullPath)) {
        res.writeHead(404, { 'Content-Type': 'text/plain' });
        res.end('Not Found');
        return;
      }

      let content = fs.readFileSync(fullPath, 'utf-8');

      if (fullPath.endsWith('.html')) {
        content = injectReloadScript(content);
      }

      const ext = path.extname(fullPath).toLowerCase();
      const contentType = mimeTypes[ext] || 'application/octet-stream';

      res.writeHead(200, { 'Content-Type': contentType });
      res.end(content);
    });

    this.server.on('upgrade', (request, socket, head) => {
      if (this.wss) {
        this.wss.handleUpgrade(request, socket, head, (ws) => {
          this.wss!.emit('connection', ws, request);
        });
      }
    });

    if (this.wss) {
      this.wss.on('connection', (ws) => {
        this.connectedClients.add(ws);
        ws.on('close', () => {
          this.connectedClients.delete(ws);
        });
      });
    }

    if (this.watcher) {
      const handleChange = (filePath: string) => {
        console.log(`File changed: ${filePath}`);
        try {
          build(ctx.contentDir, ctx.outputDir, ctx.templatesDir);
          console.log('Rebuild complete. Reloading clients...');
          for (const client of this.connectedClients) {
            if (client.readyState === WebSocket.OPEN) {
              client.send('reload');
            }
          }
        } catch (err) {
          const message = err instanceof Error ? err.message : String(err);
          console.error(`Rebuild error: ${message}`);
        }
      };

      this.watcher.on('change', handleChange);
    }
  }

  afterBuild(_pages: Page[]): void {
    for (const client of this.connectedClients) {
      if (client.readyState === WebSocket.OPEN) {
        client.send('reload');
      }
    }
  }

  onEnd(): void {
    if (this.watcher) {
      this.watcher.close();
    }
    if (this.server) {
      this.server.close();
    }
  }

  listen(port: number, callback?: () => void): http.Server {
    if (this.server) {
      this.server.listen(port, () => {
        console.log(`Dev server running at http://localhost:${port}/`);
        if (callback) callback();
      });
    }
    return this.server as http.Server;
  }

  getServer(): http.Server | null {
    return this.server;
  }
}
