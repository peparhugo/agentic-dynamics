import http from 'http';
import fs from 'fs';
import path from 'path';
import { WebSocketServer, WebSocket } from 'ws';
import { watch } from 'chokidar';
import { build } from './generator';

interface DevServerOptions {
  contentDir: string;
  outputDir: string;
  templatesDir: string;
  port: number;
}

let isBuilding = false;
let buildPending = false;

export class DevServer {
  private server: http.Server;
  private wss: WebSocketServer;
  private options: DevServerOptions;

  constructor(options: DevServerOptions) {
    this.options = options;
    this.server = http.createServer((req, res) => this.handleRequest(req, res));
    this.wss = new WebSocketServer({ server: this.server });
  }

  private async handleRequest(req: http.IncomingMessage, res: http.ServerResponse): Promise<void> {
    if (!req.url) {
      res.writeHead(404);
      res.end('Not found');
      return;
    }

    let filePath = req.url;
    if (filePath === '/') {
      filePath = 'index.html';
    } else if (filePath.startsWith('/')) {
      filePath = filePath.slice(1);
    }

    const fullPath = path.join(this.options.outputDir, filePath);

    if (!fs.existsSync(fullPath)) {
      res.writeHead(404);
      res.end('Not found');
      return;
    }

    let content = fs.readFileSync(fullPath, 'utf-8');

    if (filePath.endsWith('.html')) {
      content = this.injectLiveReloadScript(content);
    }

    const contentType = filePath.endsWith('.html') ? 'text/html' : 'application/octet-stream';
    res.writeHead(200, { 'Content-Type': contentType });
    res.end(content);
  }

  private injectLiveReloadScript(html: string): string {
    const script = `<script>
(function() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const ws = new WebSocket(protocol + '//' + window.location.host);
  ws.onmessage = function(event) {
    if (event.data === 'rebuild-complete') {
      window.location.reload();
    }
  };
})();
</script>`;

    if (html.includes('</body>')) {
      return html.replace('</body>', `${script}</body>`);
    }
    return html + script;
  }

  private notifyClients(message: string): void {
    this.wss.clients.forEach((client: WebSocket) => {
      if (client.readyState === 1) {
        client.send(message);
      }
    });
  }

  private async rebuild(): Promise<void> {
    if (isBuilding) {
      buildPending = true;
      return;
    }

    isBuilding = true;
    try {
      console.log('🔄 Rebuilding...');
      await build(this.options.contentDir, this.options.outputDir, this.options.templatesDir);
      console.log('✓ Rebuild complete');
      this.notifyClients('rebuild-complete');

      if (buildPending) {
        buildPending = false;
        await this.rebuild();
      }
    } catch (error) {
      if (error instanceof Error) {
        console.error(`✗ Build error: ${error.message}`);
      } else {
        console.error('✗ Unknown build error');
      }
    } finally {
      isBuilding = false;
    }
  }

  public start(): void {
    if (!fs.existsSync(this.options.outputDir)) {
      fs.mkdirSync(this.options.outputDir, { recursive: true });
    }

    const watcher = watch([this.options.contentDir, this.options.templatesDir], {
      ignored: /(^|[\/\\])\./,
      persistent: true,
    });

    watcher.on('change', () => {
      this.rebuild();
    });

    watcher.on('add', () => {
      this.rebuild();
    });

    watcher.on('unlink', () => {
      this.rebuild();
    });

    this.server.listen(this.options.port, () => {
      console.log(`\n🚀 Dev server running at http://localhost:${this.options.port}`);
      console.log(`📁 Watching ${this.options.contentDir} and ${this.options.templatesDir}`);
      console.log(`📦 Serving from ${this.options.outputDir}\n`);
    });
  }

  public stop(): void {
    this.server.close();
    this.wss.close();
  }
}
