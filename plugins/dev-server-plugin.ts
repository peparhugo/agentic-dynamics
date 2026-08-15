import * as fs from 'fs';
import * as http from 'http';
import * as path from 'path';
import { WebSocket, WebSocketServer } from 'ws';
import { Page } from '../src/page';
import { Plugin } from '../src/plugin';

export const LIVERELOAD_PATH = '/__livereload';

const MIME_TYPES: Record<string, string> = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.ico': 'image/x-icon',
  '.txt': 'text/plain; charset=utf-8',
};

function liveReloadScript(): string {
  return `
<script>
(function () {
  var socket = new WebSocket('ws://' + window.location.host + '${LIVERELOAD_PATH}');
  socket.addEventListener('message', function (event) {
    if (event.data === 'reload') {
      window.location.reload();
    }
  });
})();
</script>
`;
}

export function injectLiveReload(html: string): string {
  const script = liveReloadScript();
  if (html.includes('</body>')) {
    return html.replace('</body>', `${script}</body>`);
  }
  return `${html}${script}`;
}

function resolveFilePath(outputDir: string, urlPath: string): string {
  const decoded = decodeURIComponent(urlPath.split('?')[0] ?? '/');
  const relative = decoded.replace(/^\/+/, '') || 'index.html';

  let filePath = path.join(outputDir, relative);

  if (fs.existsSync(filePath) && fs.statSync(filePath).isDirectory()) {
    filePath = path.join(filePath, 'index.html');
  } else if (!fs.existsSync(filePath) && !path.extname(filePath)) {
    filePath = `${filePath}.html`;
  }

  return filePath;
}

function serveFile(outputDir: string, req: http.IncomingMessage, res: http.ServerResponse): void {
  const resolvedRoot = path.resolve(outputDir);
  const filePath = resolveFilePath(resolvedRoot, req.url ?? '/');
  const resolved = path.resolve(filePath);

  const isWithinRoot = resolved === resolvedRoot || resolved.startsWith(resolvedRoot + path.sep);
  if (!isWithinRoot || !fs.existsSync(resolved) || fs.statSync(resolved).isDirectory()) {
    res.statusCode = 404;
    res.end('Not found');
    return;
  }

  const ext = path.extname(resolved).toLowerCase();
  const contentType = MIME_TYPES[ext] ?? 'application/octet-stream';

  if (ext === '.html') {
    const html = fs.readFileSync(resolved, 'utf-8');
    res.setHeader('Content-Type', contentType);
    res.end(injectLiveReload(html));
    return;
  }

  res.setHeader('Content-Type', contentType);
  fs.createReadStream(resolved).pipe(res);
}

/**
 * Built-in plugin that serves the built output over HTTP with a live-reload
 * script injected into every HTML response, and broadcasts a reload message
 * to connected clients at the end of every build it takes part in. Starting
 * and stopping the HTTP/WebSocket server are explicit calls (`listen`,
 * `close`) rather than lifecycle hooks, since they bracket the whole dev
 * session rather than a single build pass.
 */
export class DevServerPlugin implements Plugin {
  readonly name = 'dev-server';

  private readonly outputDir: string;

  private httpServer: http.Server | null = null;

  private wss: WebSocketServer | null = null;

  constructor(outputDir: string) {
    this.outputDir = outputDir;
  }

  afterBuild(_pages: Page[]): void {
    if (!this.wss) return;
    this.wss.clients.forEach((client) => {
      if (client.readyState === WebSocket.OPEN) {
        client.send('reload');
      }
    });
  }

  listen(port: number): Promise<{ url: string; port: number }> {
    this.httpServer = http.createServer((req, res) => serveFile(this.outputDir, req, res));
    this.wss = new WebSocketServer({ server: this.httpServer, path: LIVERELOAD_PATH });

    return new Promise((resolve, reject) => {
      const server = this.httpServer as http.Server;
      server.once('error', reject);
      server.listen(port, () => {
        const address = server.address();
        const actualPort = typeof address === 'object' && address ? address.port : port;
        resolve({ url: `http://localhost:${actualPort}`, port: actualPort });
      });
    });
  }

  close(): Promise<void> {
    return new Promise((resolveClose) => {
      const wss = this.wss;
      const httpServer = this.httpServer;
      this.wss = null;
      this.httpServer = null;

      if (!wss || !httpServer) {
        resolveClose();
        return;
      }

      wss.close(() => {
        httpServer.close(() => resolveClose());
      });
    });
  }
}
