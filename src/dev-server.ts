import * as http from 'http';
import * as fs from 'fs';
import * as path from 'path';
import * as chokidar from 'chokidar';
import { WebSocketServer } from 'ws';
import { SiteGenerator } from './generator.js';

export interface DevServerOptions {
  contentDir: string;
  outputDir: string;
  templatesDir?: string;
  port?: number;
}

export class DevServer {
  private contentDir: string;
  private outputDir: string;
  private templatesDir: string;
  private port: number;
  private httpServer: http.Server | null = null;
  private wsServer: WebSocketServer | null = null;
  private generator: SiteGenerator;
  private isBuilding = false;

  constructor(options: DevServerOptions) {
    this.contentDir = options.contentDir;
    this.outputDir = options.outputDir;
    this.templatesDir = options.templatesDir || './templates';
    this.port = options.port || 3000;
    this.generator = new SiteGenerator({
      contentDir: this.contentDir,
      outputDir: this.outputDir,
      templatesDir: this.templatesDir,
    });
  }

  private async rebuild(): Promise<void> {
    if (this.isBuilding) {
      return;
    }

    this.isBuilding = true;
    try {
      console.log('🔄 Rebuilding...');
      await this.generator.build();
      console.log('✓ Rebuild complete');
      this.notifyClients();
    } catch (error) {
      console.error('Build error:', error instanceof Error ? error.message : String(error));
    } finally {
      this.isBuilding = false;
    }
  }

  private notifyClients(): void {
    if (this.wsServer) {
      this.wsServer.clients.forEach((client) => {
        client.send(JSON.stringify({ type: 'reload' }));
      });
    }
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

  private createHttpServer(): http.Server {
    return http.createServer((req, res) => {
      if (!req.url || req.method !== 'GET') {
        res.writeHead(405);
        res.end('Method Not Allowed');
        return;
      }

      let filePath = req.url === '/' ? '/index.html' : req.url;
      filePath = path.join(this.outputDir, filePath);

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
  }

  async start(): Promise<void> {
    this.httpServer = this.createHttpServer();
    this.wsServer = new WebSocketServer({ server: this.httpServer });

    this.wsServer.on('connection', (ws) => {
      console.log('📡 Client connected');
      ws.send(JSON.stringify({ type: 'connected' }));
    });

    const watcher = chokidar.watch([this.contentDir, this.templatesDir], {
      ignored: /(^|[\/\\])\.|node_modules/,
      awaitWriteFinish: {
        stabilityThreshold: 200,
        pollInterval: 100,
      },
    });

    watcher.on('change', (filePath) => {
      console.log(`📝 File changed: ${filePath}`);
      this.rebuild();
    });

    watcher.on('add', (filePath) => {
      console.log(`📝 File added: ${filePath}`);
      this.rebuild();
    });

    watcher.on('unlink', (filePath) => {
      console.log(`📝 File removed: ${filePath}`);
      this.rebuild();
    });

    return new Promise((resolve) => {
      this.httpServer!.listen(this.port, () => {
        console.log(`\n🚀 Dev server running on http://localhost:${this.port}`);
        console.log(`👀 Watching ${this.contentDir} and ${this.templatesDir} for changes...\n`);
      });
    });
  }

  async stop(): Promise<void> {
    return new Promise((resolve) => {
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
