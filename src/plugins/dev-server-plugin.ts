import http from 'http';
import fs from 'fs';
import path from 'path';
import { WebSocketServer, WebSocket } from 'ws';
import { watch } from 'chokidar';
import { Plugin, PluginContext } from '../plugin';

export interface DevServerPluginOptions {
  port?: number;
}

let isBuilding = false;
let buildPending = false;

export class DevServerPlugin implements Plugin {
  name = 'dev-server-plugin';
  private server: http.Server | undefined;
  private wss: WebSocketServer | undefined;
  private port: number;
  private isRunning = false;
  private buildCallback: (() => Promise<void>) | undefined;

  constructor(options: DevServerPluginOptions = {}) {
    this.port = options.port || 3000;
  }

  async onStart(context: PluginContext): Promise<void> {
    const outputDir = context.outputDir as string;

    if (!fs.existsSync(outputDir)) {
      fs.mkdirSync(outputDir, { recursive: true });
    }

    this.server = http.createServer((req, res) => this.handleRequest(req, res, outputDir));
    this.wss = new WebSocketServer({ server: this.server });

    const contentDir = context.contentDir as string;
    const templatesDir = context.templatesDir as string;

    const watcher = watch([contentDir, templatesDir], {
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
  }

  async afterBuild(context: PluginContext): Promise<void> {
    if (this.isRunning) return;

    this.isRunning = true;
    this.server?.listen(this.port, () => {
      console.log(`\n🚀 Dev server running at http://localhost:${this.port}`);
      console.log(`📁 Watching ${context.contentDir} and ${context.templatesDir}`);
      console.log(`📦 Serving from ${context.outputDir}\n`);
    });
  }

  setBuildCallback(callback: () => Promise<void>): void {
    this.buildCallback = callback;
  }

  private async rebuild(): Promise<void> {
    if (!this.buildCallback) return;

    if (isBuilding) {
      buildPending = true;
      return;
    }

    isBuilding = true;
    try {
      console.log('🔄 Rebuilding...');
      await this.buildCallback();
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

  private async handleRequest(req: http.IncomingMessage, res: http.ServerResponse, outputDir: string): Promise<void> {
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

    const fullPath = path.join(outputDir, filePath);

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
    if (!this.wss) return;
    this.wss.clients.forEach((client: WebSocket) => {
      if (client.readyState === 1) {
        client.send(message);
      }
    });
  }

  stop(): void {
    this.server?.close();
    this.wss?.close();
  }
}
