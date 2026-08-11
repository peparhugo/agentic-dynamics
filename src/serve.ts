import * as http from 'http';
import * as fs from 'fs';
import * as path from 'path';
import { WebSocketServer, WebSocket } from 'ws';
import * as chokidar from 'chokidar';
import { build } from './build';

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

export interface ServeOptions {
  content?: string;
  output?: string;
  templates?: string;
  port?: number;
}

export function serve(options: ServeOptions): http.Server {
  const contentDir = options.content || './content';
  const outputDir = options.output || './dist';
  const templatesDir = options.templates || './templates';
  const port = options.port || 3000;

  build(contentDir, outputDir, templatesDir);

  const watcher = chokidar.watch([contentDir, templatesDir], {
    ignoreInitial: true,
  });

  const wss = new WebSocketServer({ noServer: true });

  const mimeTypes: Record<string, string> = {
    '.html': 'text/html',
    '.css': 'text/css',
    '.js': 'application/javascript',
    '.json': 'application/json',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.svg': 'image/svg+xml',
  };

  const server = http.createServer((req, res) => {
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

  server.on('upgrade', (request, socket, head) => {
    wss.handleUpgrade(request, socket, head, (ws) => {
      wss.emit('connection', ws, request);
    });
  });

  const connectedClients = new Set<WebSocket>();

  wss.on('connection', (ws) => {
    connectedClients.add(ws);
    ws.on('close', () => {
      connectedClients.delete(ws);
    });
  });

  watcher.on('change', (filePath) => {
    console.log(`File changed: ${filePath}`);
    try {
      build(contentDir, outputDir, templatesDir);
      console.log('Rebuild complete. Reloading clients...');
      for (const client of connectedClients) {
        if (client.readyState === WebSocket.OPEN) {
          client.send('reload');
        }
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      console.error(`Rebuild error: ${message}`);
    }
  });

  server.listen(port, () => {
    console.log(`Dev server running at http://localhost:${port}/`);
  });

  return server;
}
