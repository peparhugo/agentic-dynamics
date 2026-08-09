import http from 'http';
import fs from 'fs';
import path from 'path';
import { WebSocketServer, WebSocket } from 'ws';
import chokidar from 'chokidar';
import { Generator } from './generator';
import { CLIOptions } from './types';

const RELOAD_SCRIPT = `
<script>
(function() {
  var ws = new WebSocket('ws://' + location.host + '/__livereload');
  ws.onmessage = function(msg) {
    if (msg.data === 'reload') location.reload();
  };
  ws.onclose = function() {
    setTimeout(function() { location.reload(); }, 2000);
  };
})();
</script>
`;

function injectReloadScript(html: string): string {
  if (html.includes('</body>')) {
    return html.replace('</body>', RELOAD_SCRIPT + '</body>');
  }
  return html + RELOAD_SCRIPT;
}

const MIME_TYPES: Record<string, string> = {
  '.html': 'text/html',
  '.css': 'text/css',
  '.js': 'application/javascript',
  '.json': 'application/json',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.xml': 'application/xml',
  '.txt': 'text/plain',
};

export function startDevServer(options: CLIOptions): void {
  const generator = new Generator(options);
  generator.generate();

  let wsClients: WebSocket[] = [];

  const server = http.createServer((req, res) => {
    if (!req.url) {
      res.writeHead(400);
      res.end();
      return;
    }

    if (req.url === '/__livereload') {
      return;
    }

    let filePath = path.join(options.output, req.url === '/' ? 'index.html' : req.url);

    if (!fs.existsSync(filePath)) {
      filePath = path.join(options.output, req.url, 'index.html');
    }

    if (!fs.existsSync(filePath)) {
      filePath = path.join(options.output, 'index.html');
    }

    if (!fs.existsSync(filePath)) {
      res.writeHead(404, { 'Content-Type': 'text/html' });
      res.end('<h1>404 - Not Found</h1>');
      return;
    }

    const stat = fs.statSync(filePath);
    if (stat.isDirectory()) {
      filePath = path.join(filePath, 'index.html');
    }

    let content: string | Buffer;
    try {
      content = fs.readFileSync(filePath);
    } catch {
      res.writeHead(404, { 'Content-Type': 'text/html' });
      res.end('<h1>404 - Not Found</h1>');
      return;
    }

    const ext = path.extname(filePath);

    if (ext === '.html' || filePath.endsWith('.html')) {
      content = injectReloadScript(content.toString('utf-8'));
      res.writeHead(200, {
        'Content-Type': 'text/html',
        'Content-Length': Buffer.byteLength(content),
      });
      res.end(content);
    } else {
      res.writeHead(200, {
        'Content-Type': MIME_TYPES[ext] || 'application/octet-stream',
        'Content-Length': stat.size,
      });
      res.end(content);
    }
  });

  const wss = new WebSocketServer({ server, path: '/__livereload' });

  wss.on('connection', (ws) => {
    wsClients.push(ws);
    ws.on('close', () => {
      wsClients = wsClients.filter(c => c !== ws);
    });
  });

  function reloadClients(): void {
    try {
      generator.generate();
    } catch (err) {
      console.error('Generation error:', err);
      return;
    }

    for (const client of wsClients) {
      if (client.readyState === WebSocket.OPEN) {
        client.send('reload');
      }
    }
    console.log(`[reload] ${wsClients.length} client(s) notified`);
  }

  const watcher = chokidar.watch([options.source, options.templates], {
    ignoreInitial: true,
    awaitWriteFinish: {
      stabilityThreshold: 100,
      pollInterval: 50,
    },
  });

  let debounceTimer: ReturnType<typeof setTimeout>;
  watcher.on('all', (event, filePath) => {
    console.log(`[${event}] ${filePath}`);
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(reloadClients, 150);
  });

  server.listen(options.port, () => {
    console.log(`Dev server running at http://localhost:${options.port}`);
  });
}
