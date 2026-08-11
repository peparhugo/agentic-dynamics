import http from 'http';
import fs from 'fs';
import path from 'path';
import { WebSocketServer, WebSocket } from 'ws';
import chokidar from 'chokidar';
import { parseMarkdownFiles } from './parser';
import { generateSite } from './generator';

export interface ServeOptions {
  content: string;
  output: string;
  templates: string;
  port: number;
}

function rebuild(content: string, output: string, templates: string): number {
  const pages = parseMarkdownFiles(content);
  generateSite(pages, output, templates);
  return pages.length;
}

function getMimeType(filePath: string): string {
  const ext = path.extname(filePath).toLowerCase();
  const mimes: Record<string, string> = {
    '.html': 'text/html',
    '.css': 'text/css',
    '.js': 'application/javascript',
    '.json': 'application/json',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif': 'image/gif',
    '.svg': 'image/svg+xml',
  };
  return mimes[ext] || 'application/octet-stream';
}

function injectLiveReload(html: string, port: number): string {
  const script = `<script>
(function() {
  var ws = new WebSocket('ws://localhost:${port}');
  ws.onmessage = function(msg) {
    if (msg.data === 'reload') {
      location.reload();
    }
  };
})();
</script>`;
  return html.replace('</body>', script + '\n</body>');
}

export function createServer(options: ServeOptions): http.Server {
  const { content, output, templates, port } = options;
  const resolvedOutput = path.resolve(output);

  rebuild(content, output, templates);

  const server = http.createServer((req, res) => {
    const url = req.url || '/';
    const sanitized = path.normalize(url).replace(/^(\.\.[/\\])+/, '');
    const relativePath = sanitized.replace(/^[/\\]+/, '');
    const filePath = relativePath
      ? path.join(resolvedOutput, relativePath)
      : path.join(resolvedOutput, 'index.html');

    try {
      if (!fs.existsSync(filePath) || !fs.statSync(filePath).isFile()) {
        res.writeHead(404);
        res.end('Not found');
        return;
      }

      const ext = path.extname(filePath).toLowerCase();
      const content = fs.readFileSync(filePath);

      if (ext === '.html') {
        const addr = server.address();
        const actualPort = typeof addr === 'object' && addr ? addr.port : port;
        const html = injectLiveReload(content.toString('utf-8'), actualPort);
        res.writeHead(200, { 'Content-Type': 'text/html' });
        res.end(html);
      } else {
        res.writeHead(200, { 'Content-Type': getMimeType(filePath) });
        res.end(content);
      }
    } catch {
      res.writeHead(500);
      res.end('Internal server error');
    }
  });

  const wss = new WebSocketServer({ server });

  const resolvedContent = path.resolve(content);
  const resolvedTemplates = path.resolve(templates);

  const watcher = chokidar.watch([resolvedContent, resolvedTemplates], {
    ignoreInitial: true,
  });

  watcher.on('all', () => {
    rebuild(content, output, templates);
    wss.clients.forEach((client) => {
      if (client.readyState === WebSocket.OPEN) {
        client.send('reload');
      }
    });
  });

  (server as any)._watcher = watcher;
  (server as any)._wss = wss;

  return server;
}

export function serve(options: ServeOptions): http.Server {
  const server = createServer(options);
  server.listen(options.port, () => {
    console.log(`Dev server running at http://localhost:${options.port}`);
  });
  return server;
}
