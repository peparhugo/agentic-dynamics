import http from 'http';
import fs from 'fs';
import path from 'path';
import { WebSocketServer, WebSocket } from 'ws';
import chokidar from 'chokidar';
import { Plugin, BuildContext } from '../plugin.js';

const LIVE_RELOAD_SCRIPT = `
<script>
(function() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const ws = new WebSocket(protocol + '//' + window.location.host + '/__live-reload__');

  ws.onmessage = function(event) {
    if (event.data === 'reload') {
      window.location.reload();
    }
  };

  ws.onclose = function() {
    setTimeout(function() {
      window.location.reload();
    }, 1000);
  };
})();
</script>
`;

export interface DevServerPluginOptions {
  port?: number;
  onRebuild?: () => Promise<void>;
  test?: boolean;
}

export class DevServerPlugin implements Plugin {
  name = 'dev-server';
  private port: number;
  private server: http.Server | null = null;
  private wss: WebSocketServer | null = null;
  private watcher: any = null;
  private clients: Set<WebSocket> = new Set();
  private isRebuilding = false;
  private onRebuild?: () => Promise<void>;
  private test: boolean;

  constructor(options: DevServerPluginOptions = {}) {
    this.port = options.port || 3000;
    this.onRebuild = options.onRebuild;
    this.test = options.test || false;
    this.onStart = this.onStart.bind(this);
    this.onEnd = this.onEnd.bind(this);
  }

  async onStart(context: BuildContext): Promise<void> {
    const { contentDir, outputDir, templatesDir = './templates' } = context;

    const rebuildSite = async () => {
      if (this.isRebuilding) return;
      this.isRebuilding = true;

      try {
        if (this.onRebuild) {
          await this.onRebuild();
        }
        console.log('Site rebuilt successfully');

        this.clients.forEach(client => {
          if (client.readyState === 1) {
            client.send('reload');
          }
        });
      } catch (error) {
        console.error('Error rebuilding site:', error instanceof Error ? error.message : error);
      } finally {
        this.isRebuilding = false;
      }
    };

    this.server = http.createServer((req, res) => {
      if (req.url === '/__live-reload__') {
        res.writeHead(404);
        res.end();
        return;
      }

      let filePath = path.join(outputDir, (req.url === '/' || !req.url) ? 'index.html' : req.url);

      if (filePath.endsWith('/')) {
        filePath = path.join(filePath, 'index.html');
      }

      if (!fs.existsSync(filePath)) {
        res.writeHead(404);
        res.end('Not Found');
        return;
      }

      let content = fs.readFileSync(filePath, 'utf-8');

      if (filePath.endsWith('.html')) {
        content = content.replace('</body>', LIVE_RELOAD_SCRIPT + '</body>');
      }

      const ext = path.extname(filePath);
      const mimeTypes: Record<string, string> = {
        '.html': 'text/html',
        '.css': 'text/css',
        '.js': 'application/javascript',
        '.json': 'application/json',
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.gif': 'image/gif',
        '.svg': 'image/svg+xml'
      };

      const contentType = mimeTypes[ext] || 'text/plain';
      res.writeHead(200, { 'Content-Type': contentType });
      res.end(content);
    });

    this.wss = new WebSocketServer({ server: this.server });

    this.wss.on('connection', (ws: WebSocket) => {
      this.clients.add(ws);

      ws.on('close', () => {
        this.clients.delete(ws);
      });
    });

    this.watcher = chokidar.watch([contentDir, templatesDir], {
      ignored: /(^|[/\\])\.|node_modules/,
      persistent: true,
      awaitWriteFinish: {
        stabilityThreshold: 100,
        pollInterval: 100
      }
    });

    this.watcher.on('change', () => {
      rebuildSite();
    });

    this.watcher.on('add', () => {
      rebuildSite();
    });

    this.watcher.on('unlink', () => {
      rebuildSite();
    });

    await new Promise<void>(resolve => {
      this.server!.listen(this.port, () => {
        if (!this.test) {
          console.log(`Dev server running at http://localhost:${this.port}`);
          console.log(`Watching ${contentDir} and ${templatesDir} for changes`);
        }
        resolve();
      });
    });

    if (!this.test) {
      process.on('SIGINT', () => {
        console.log('\nShutting down...');
        this.watcher.close();
        this.server!.close();
        process.exit(0);
      });
    }
  }

  async onEnd(context: BuildContext): Promise<void> {
    if (this.watcher) {
      this.watcher.close();
    }
    if (this.server) {
      await new Promise<void>(resolve => {
        this.server!.close(() => resolve());
      });
    }
  }
}
