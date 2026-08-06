import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { WebSocketServer } from 'ws';
import chokidar from 'chokidar';
import type { SiteConfig } from './types.js';
import { generate } from './generator.js';

const RELOAD_SCRIPT = `
<script>
  (function() {
    var ws = new WebSocket('ws://' + location.host + '/__reload');
    ws.onmessage = function(msg) {
      if (msg.data === 'reload') location.reload();
    };
    ws.onclose = function() {
      setTimeout(function() {
        (function() {
          var ws = new WebSocket('ws://' + location.host + '/__reload');
          ws.onmessage = function(msg) {
            if (msg.data === 'reload') location.reload();
          };
        })();
      }, 1000);
    };
  })();
</script>`;

const MIME_TYPES: Record<string, string> = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.svg': 'image/svg+xml',
  '.xml': 'application/xml; charset=utf-8',
  '.ico': 'image/x-icon',
};

export function startDevServer(config: SiteConfig, port: number = 8080): void {
  generate(config, true);

  const server = http.createServer((req, res) => {
    if (!req.url) {
      res.writeHead(400);
      res.end();
      return;
    }

    const urlPath = req.url.split('?')[0];
    const filePath = urlPath === '/' || urlPath === ''
      ? path.join(config.output, 'index.html')
      : path.join(config.output, urlPath);

    const ext = path.extname(filePath).toLowerCase();

    try {
      const content = fs.readFileSync(filePath);
      res.writeHead(200, { 'Content-Type': MIME_TYPES[ext] || 'application/octet-stream' });
      res.end(content);
    } catch {
      if (ext === '.html' || ext === '') {
        try {
          const htmlPath = filePath.endsWith('.html') ? filePath : filePath + '.html';
          const content = fs.readFileSync(htmlPath);
          res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
          res.end(content);
        } catch {
          res.writeHead(404, { 'Content-Type': 'text/html; charset=utf-8' });
          res.end('<h1>404 - Not Found</h1>');
        }
      } else {
        res.writeHead(404);
        res.end();
      }
    }
  });

  const wss = new WebSocketServer({ server, path: '/__reload' });

  wss.on('connection', (ws) => {
    ws.on('error', () => {});
  });

  const watcher = chokidar.watch([
    path.join(config.src, '**/*.md'),
    path.join(config.templates, '**/*.{hbs,handlebars}'),
  ], {
    ignoreInitial: true,
    awaitWriteFinish: { stabilityThreshold: 100, pollInterval: 50 },
  });

  function rebroadcast() {
    for (const client of wss.clients) {
      if (client.readyState === 1) {
        client.send('reload');
      }
    }
  }

  watcher.on('change', () => {
    generate(config, true);
    rebroadcast();
  });

  watcher.on('add', () => {
    generate(config, true);
    rebroadcast();
  });

  watcher.on('unlink', () => {
    generate(config, true);
    rebroadcast();
  });

  server.listen(port, () => {
    console.log(`Dev server running at http://localhost:${port}`);
    console.log(`Watching for changes in ${config.src} and ${config.templates}`);
  });
}
