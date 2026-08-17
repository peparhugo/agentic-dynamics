import http from 'http';
import { promises as fs } from 'fs';
import path from 'path';
import chokidar, { type FSWatcher } from 'chokidar';
import { WebSocketServer, WebSocket } from 'ws';
import { runBuild, setupBuild } from '../generate';
import type { Plugin } from '../plugin';

export interface ServeOptions {
  content: string;
  output: string;
  templates: string;
  port: number;
}

export interface DevServer {
  port: number;
  close(): Promise<void>;
}

const RELOAD_CLIENT = `<script>(function(){var s=new WebSocket('ws://'+location.host);s.onmessage=function(e){if(e.data==='reload')location.reload();};})();</script>`;

const MIME_TYPES: Record<string, string> = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.mjs': 'application/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.ico': 'image/x-icon',
  '.webp': 'image/webp',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
  '.txt': 'text/plain; charset=utf-8',
};

export function injectReloadScript(html: string): string {
  if (html.includes('</body>')) {
    return html.replace('</body>', `${RELOAD_CLIENT}</body>`);
  }
  return `${html}${RELOAD_CLIENT}`;
}

export class DevServerPlugin implements Plugin {
  name = 'dev-server';

  async serve(options: ServeOptions): Promise<DevServer> {
    const { content, output, templates, port } = options;

    const { context, pipeline, templatePlugin } = await setupBuild(content, output, templates);

    await pipeline.onStart();
    await pipeline.beforeBuild();
    await runBuild(context, pipeline, templatePlugin);

    const wss = new WebSocketServer({ noServer: true });

    const server = http.createServer(async (req, res) => {
      try {
        const url = new URL(req.url ?? '/', 'http://localhost');
        let pathname = decodeURIComponent(url.pathname);
        if (pathname === '/') {
          pathname = '/index.html';
        }

        const root = path.resolve(output);
        const target = path.resolve(root, `.${pathname}`);
        if (target !== root && !target.startsWith(`${root}${path.sep}`)) {
          res.writeHead(403, { 'Content-Type': 'text/plain; charset=utf-8' });
          res.end('Forbidden');
          return;
        }

        const data = await fs.readFile(target);
        const ext = path.extname(target).toLowerCase();
        const contentType = MIME_TYPES[ext] ?? 'application/octet-stream';

        if (ext === '.html') {
          res.writeHead(200, { 'Content-Type': contentType });
          res.end(injectReloadScript(data.toString('utf8')));
          return;
        }

        res.writeHead(200, { 'Content-Type': contentType });
        res.end(data);
      } catch {
        res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
        res.end('Not Found');
      }
    });

    server.on('upgrade', (req, socket, head) => {
      wss.handleUpgrade(req, socket, head, (ws) => {
        wss.emit('connection', ws, req);
      });
    });

    const watcher: FSWatcher = chokidar.watch([content, templates], {
      ignoreInitial: true,
    });

    let rebuildTimer: NodeJS.Timeout | null = null;

    const broadcast = (message: string): void => {
      for (const client of wss.clients) {
        if (client.readyState === WebSocket.OPEN) {
          client.send(message);
        }
      }
    };

    const scheduleRebuild = (): void => {
      if (rebuildTimer) {
        clearTimeout(rebuildTimer);
      }
      rebuildTimer = setTimeout(() => {
        rebuildTimer = null;
        (async () => {
          try {
            await pipeline.beforeBuild();
            await runBuild(context, pipeline, templatePlugin);
            broadcast('reload');
          } catch {
            /* ignore rebuild errors so the watcher keeps running */
          }
        })();
      }, 100);
    };

    watcher.on('add', scheduleRebuild);
    watcher.on('change', scheduleRebuild);
    watcher.on('unlink', scheduleRebuild);

    await new Promise<void>((resolve, reject) => {
      server.once('error', reject);
      server.listen(port, () => {
        server.removeListener('error', reject);
        resolve();
      });
    });

    const address = server.address();
    const actualPort = typeof address === 'object' && address !== null ? address.port : port;

    return {
      port: actualPort,
      close: async (): Promise<void> => {
        if (rebuildTimer) {
          clearTimeout(rebuildTimer);
          rebuildTimer = null;
        }
        await watcher.close();
        for (const client of wss.clients) {
          client.terminate();
        }
        await new Promise<void>((resolve) => {
          wss.close(() => resolve());
        });
        await new Promise<void>((resolve, reject) => {
          server.close((err) => (err ? reject(err) : resolve()));
        });
        await pipeline.onEnd();
      },
    };
  }
}
