import fs from 'fs';
import http from 'http';
import path from 'path';
import { AddressInfo } from 'net';

import chokidar, { FSWatcher } from 'chokidar';
import { WebSocketServer, WebSocket } from 'ws';

import { buildSite } from './site';

export interface ServeOptions {
  content?: string;
  output?: string;
  templates?: string;
  port?: number;
  host?: string;
}

export interface ServeHandle {
  server: http.Server;
  wss: WebSocketServer;
  watcher: FSWatcher;
  port: number;
  host: string;
  address: string;
  outputDir: string;
  close: () => Promise<void>;
  rebuild: () => void;
}

export const LIVE_RELOAD_PATH = '/__ssg_livereload';

function liveReloadScript(): string {
  return `<script data-ssg-livereload>
(function () {
  var protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  var ws = new WebSocket(protocol + '//' + location.host + '${LIVE_RELOAD_PATH}');
  ws.addEventListener('message', function (event) {
    if (event.data === 'reload') {
      location.reload();
    }
  });
})();
</script>`;
}

export function injectLiveReloadScript(html: string): string {
  const script = liveReloadScript();
  if (html.includes('</body>')) {
    return html.replace('</body>', `${script}\n</body>`);
  }
  if (html.includes('</html>')) {
    return html.replace('</html>', `${script}\n</html>`);
  }
  return html + script;
}

const MIME_TYPES: Record<string, string> = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.mjs': 'application/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.map': 'application/json; charset=utf-8',
  '.txt': 'text/plain; charset=utf-8',
  '.md': 'text/markdown; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.ico': 'image/x-icon',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
  '.ttf': 'font/ttf',
  '.eot': 'application/vnd.ms-fontobject',
  '.xml': 'application/xml; charset=utf-8',
};

export async function startServer(options: ServeOptions = {}): Promise<ServeHandle> {
  const contentDir = path.resolve(options.content ?? './content');
  const outputDir = path.resolve(options.output ?? './dist');
  const templatesDir = path.resolve(options.templates ?? './templates');
  const host = options.host ?? 'localhost';
  const requestedPort = options.port ?? 3000;

  const rebuild = (): void => {
    try {
      buildSite({ contentDir, outputDir, templatesDir });
    } catch (err) {
      console.error('Rebuild failed:', err);
    }
  };

  const server = http.createServer((req, res) => {
    const raw = req.url ?? '/';
    const queryIndex = raw.indexOf('?');
    const rawPath = queryIndex === -1 ? raw : raw.slice(0, queryIndex);
    let pathname = decodeURIComponent(rawPath);
    if (pathname === '/') {
      pathname = '/index.html';
    }
    const relative = pathname.replace(/^\/+/, '');
    const filePath = path.resolve(outputDir, relative);
    if (filePath !== outputDir && !filePath.startsWith(outputDir + path.sep)) {
      res.statusCode = 403;
      res.setHeader('Content-Type', 'text/plain; charset=utf-8');
      res.end('Forbidden');
      return;
    }
    fs.readFile(filePath, (err, data) => {
      if (err) {
        res.statusCode = 404;
        res.setHeader('Content-Type', 'text/plain; charset=utf-8');
        res.end('Not Found');
        return;
      }
      const ext = path.extname(filePath).toLowerCase();
      res.setHeader('Content-Type', MIME_TYPES[ext] ?? 'application/octet-stream');
      if (ext === '.html') {
        data = Buffer.from(injectLiveReloadScript(data.toString('utf-8')));
      }
      res.end(data);
    });
  });

  const wss = new WebSocketServer({ server, path: LIVE_RELOAD_PATH });

  let closed = false;
  let rebuildTimer: NodeJS.Timeout | null = null;

  const broadcastReload = (): void => {
    for (const client of wss.clients) {
      if (client.readyState === WebSocket.OPEN) {
        client.send('reload');
      }
    }
  };

  const scheduleRebuild = (): void => {
    if (rebuildTimer) {
      clearTimeout(rebuildTimer);
    }
    rebuildTimer = setTimeout(() => {
      rebuildTimer = null;
      rebuild();
      broadcastReload();
    }, 150);
  };

  const watcher = chokidar.watch([contentDir, templatesDir], {
    ignoreInitial: true,
    ignored: (watchedPath: string) => {
      const resolved = path.resolve(watchedPath);
      return resolved === outputDir || resolved.startsWith(outputDir + path.sep);
    },
  });

  watcher.on('add', scheduleRebuild);
  watcher.on('change', scheduleRebuild);
  watcher.on('unlink', scheduleRebuild);
  watcher.on('addDir', scheduleRebuild);
  watcher.on('unlinkDir', scheduleRebuild);

  rebuild();

  await new Promise<void>((resolve, reject) => {
    server.once('error', reject);
    server.listen(requestedPort, host, () => {
      resolve();
    });
  });

  const address = server.address() as AddressInfo;

  const close = (): Promise<void> => {
    return new Promise((resolve) => {
      if (closed) {
        resolve();
        return;
      }
      closed = true;
      if (rebuildTimer) {
        clearTimeout(rebuildTimer);
        rebuildTimer = null;
      }
      for (const client of wss.clients) {
        client.terminate();
      }
      watcher.close().then(() => {
        wss.close(() => {
          server.close(() => resolve());
        });
      });
    });
  };

  return {
    server,
    wss,
    watcher,
    port: address.port,
    host,
    address: `http://${host}:${address.port}`,
    outputDir,
    close,
    rebuild,
  };
}
