import * as http from 'http';
import * as fs from 'fs';
import * as path from 'path';
import * as chokidar from 'chokidar';
import { WebSocketServer } from 'ws';
import { Plugin, PluginContext } from '../plugin.js';

export interface DevServerOptions {
  port?: number;
  onRebuild?: () => Promise<void>;
}

export class DevServerPlugin implements Plugin {
  name = 'dev-server';
  version = '1.0.0';
  private httpServer: http.Server | null = null;
  private wsServer: WebSocketServer | null = null;
  private options: DevServerOptions;
  private watcher: chokidar.FSWatcher | null = null;

  constructor(options: DevServerOptions = {}) {
    this.options = options;
  }

  async onStart(context: PluginContext): Promise<void> {
    this.setupHttpServer(context);
  }

  async onEnd(context: PluginContext): Promise<void> {
    await this.stop();
  }

  private setupHttpServer(context: PluginContext): void {
    const port = this.options.port || 3000;
    const outputDir = context.outputDir;

    this.httpServer = http.createServer((req, res) => {
      if (!req.url || req.method !== 'GET') {
        res.writeHead(405);
        res.end('Method Not Allowed');
        return;
      }

      let filePath = req.url === '/' ? '/index.html' : req.url;
      filePath = path.join(outputDir, filePath);

      try {
        if (!fs.existsSync(filePath)) {
          res.writeHead(404);
          res.end('Not Found');
          return;
        }

        const stat = fs.statSync(filePath);
        if (stat.isDirectory()) {
          filePath = path.join(filePath, 'index.html');
          if (!fs.existsSync(filePath)) {
            res.writeHead(404);
            res.end('Not Found');
            return;
          }
        }

        const content = fs.readFileSync(filePath, 'utf-8');
        const contentType = filePath.endsWith('.html') ? 'text/html' : 'application/octet-stream';

        let responseContent = content;
        if (filePath.endsWith('.html')) {
          responseContent = this.injectLiveReloadScript(content);
        }

        res.writeHead(200, { 'Content-Type': contentType });
        res.end(responseContent);
      } catch (error) {
        console.error('Server error:', error);
        res.writeHead(500);
        res.end('Internal Server Error');
      }
    });

    this.wsServer = new WebSocketServer({ server: this.httpServer });

    this.wsServer.on('connection', (ws) => {
      console.log('📡 Client connected');
      ws.send(JSON.stringify({ type: 'connected' }));
    });

    this.setupWatcher(context);

    this.httpServer.listen(port, () => {
      console.log(`\n🚀 Dev server running on http://localhost:${port}`);
      console.log(`👀 Watching ${context.contentDir} and ${context.templatesDir} for changes...\n`);
    });
  }

  private setupWatcher(context: PluginContext): void {
    this.watcher = chokidar.watch([context.contentDir, context.templatesDir || ''], {
      ignored: /(^|[\/\\])\.|node_modules/,
      awaitWriteFinish: {
        stabilityThreshold: 200,
        pollInterval: 100,
      },
    });

    let isBuilding = false;

    const rebuild = async () => {
      if (isBuilding) {
        return;
      }

      isBuilding = true;
      try {
        console.log('🔄 Rebuilding...');
        if (this.options.onRebuild) {
          await this.options.onRebuild();
        }
        console.log('✓ Rebuild complete');
        this.notifyClients();
      } catch (error) {
        console.error('Build error:', error instanceof Error ? error.message : String(error));
      } finally {
        isBuilding = false;
      }
    };

    this.watcher.on('change', (filePath) => {
      console.log(`📝 File changed: ${filePath}`);
      rebuild();
    });

    this.watcher.on('add', (filePath) => {
      console.log(`📝 File added: ${filePath}`);
      rebuild();
    });

    this.watcher.on('unlink', (filePath) => {
      console.log(`📝 File removed: ${filePath}`);
      rebuild();
    });
  }

  private injectLiveReloadScript(html: string): string {
    const liveReloadScript = `
<script>
(function() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const ws = new WebSocket(protocol + '//' + window.location.host);

  ws.onmessage = function(event) {
    const message = JSON.parse(event.data);
    if (message.type === 'reload') {
      console.log('[Live Reload] Reloading page...');
      window.location.reload();
    }
  };

  ws.onerror = function(error) {
    console.error('[Live Reload] WebSocket error:', error);
  };

  ws.onopen = function() {
    console.log('[Live Reload] Connected');
  };
})();
</script>
`;
    return html.replace('</body>', liveReloadScript + '</body>');
  }

  private notifyClients(): void {
    if (this.wsServer) {
      this.wsServer.clients.forEach((client) => {
        client.send(JSON.stringify({ type: 'reload' }));
      });
    }
  }

  async stop(): Promise<void> {
    return new Promise((resolve) => {
      if (this.watcher) {
        this.watcher.close();
      }
      if (this.httpServer) {
        this.httpServer.close(() => {
          console.log('Dev server stopped');
          resolve();
        });
      } else {
        resolve();
      }
    });
  }
}
