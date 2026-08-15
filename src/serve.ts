import http from 'http';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { WebSocketServer } from 'ws';
import chokidar from 'chokidar';
import { generate } from './generator.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export interface ServeOptions {
  contentDir: string;
  outputDir: string;
  port?: number;
  templatesDir?: string;
  layoutsDir?: string;
  partialsDir?: string;
}

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

export interface ServeResult {
  close: () => Promise<void>;
}

export async function serve(options: ServeOptions, test?: boolean): Promise<ServeResult> {
  const port = options.port || 3000;
  const { contentDir, outputDir } = options;
  const templatesDir = options.templatesDir || './templates';
  const layoutsDir = options.layoutsDir || './templates/layouts';
  const partialsDir = options.partialsDir || './templates/partials';

  let isRebuilding = false;
  const clients: Set<any> = new Set();

  const rebuildSite = async () => {
    if (isRebuilding) return;
    isRebuilding = true;

    try {
      await generate({
        contentDir,
        outputDir,
        templatesDir,
        layoutsDir,
        partialsDir
      });
      console.log('Site rebuilt successfully');

      clients.forEach(client => {
        if (client.readyState === 1) {
          client.send('reload');
        }
      });
    } catch (error) {
      console.error('Error rebuilding site:', error instanceof Error ? error.message : error);
    } finally {
      isRebuilding = false;
    }
  };

  const server = http.createServer((req, res) => {
    if (req.url === '/__live-reload__') {
      res.writeHead(404);
      res.end();
      return;
    }

    let filePath = path.join(outputDir, req.url === '/' ? 'index.html' : req.url);

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

  const wss = new WebSocketServer({ server });

  wss.on('connection', (ws) => {
    clients.add(ws);

    ws.on('close', () => {
      clients.delete(ws);
    });
  });

  const watcher = chokidar.watch([contentDir, templatesDir], {
    ignored: /(^|[/\\])\.|node_modules/,
    persistent: true,
    awaitWriteFinish: {
      stabilityThreshold: 100,
      pollInterval: 100
    }
  });

  watcher.on('change', () => {
    rebuildSite();
  });

  watcher.on('add', () => {
    rebuildSite();
  });

  watcher.on('unlink', () => {
    rebuildSite();
  });

  await new Promise<void>(resolve => {
    server.listen(port, () => {
      if (!test) {
        console.log(`Dev server running at http://localhost:${port}`);
        console.log(`Watching ${contentDir} and ${templatesDir} for changes`);
      }
      resolve();
    });
  });

  if (!test) {
    process.on('SIGINT', () => {
      console.log('\nShutting down...');
      watcher.close();
      server.close();
      process.exit(0);
    });
  }

  return {
    close: async () => {
      await new Promise<void>(resolve => {
        watcher.close();
        server.close(() => resolve());
      });
    }
  };
}
