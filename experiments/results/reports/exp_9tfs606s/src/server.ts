import chokidar from 'chokidar';
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { WebSocketServer, WebSocket } from 'ws';
import { buildSite } from './build.js';
import type { SiteConfig } from './types.js';

const MIME: Record<string, string> = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json',
  '.xml': 'application/xml; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.webp': 'image/webp',
  '.ico': 'image/x-icon',
  '.txt': 'text/plain; charset=utf-8',
  '.woff2': 'font/woff2',
};

export function reloadScript(port: number): string {
  return `<script>
(function () {
  function connect() {
    var ws = new WebSocket('ws://' + location.hostname + ':${port}');
    ws.onmessage = function (e) { if (e.data === 'reload') location.reload(); };
    ws.onclose = function () { setTimeout(connect, 1000); };
  }
  connect();
})();
</script>`;
}

/** Inject the live-reload script before </body> (or append if absent). */
export function injectReloadScript(html: string, port: number): string {
  const script = reloadScript(port);
  if (html.includes('</body>')) return html.replace('</body>', `${script}\n</body>`);
  return html + script;
}

export interface DevServer {
  close(): Promise<void>;
  port: number;
}

/** Resolve a request path to a file inside root, guarding against traversal. */
export function resolveRequestPath(root: string, urlPath: string): string | null {
  const decoded = decodeURIComponent(urlPath.split('?')[0] ?? '/');
  let rel = path.posix.normalize(decoded).replace(/^\/+/, '');
  if (rel.startsWith('..')) return null;
  let full = path.resolve(root, rel);
  if (!full.startsWith(path.resolve(root))) return null;
  if (fs.existsSync(full) && fs.statSync(full).isDirectory()) {
    full = path.join(full, 'index.html');
  }
  return fs.existsSync(full) && fs.statSync(full).isFile() ? full : null;
}

/**
 * Start the dev server: initial build, static file serving with reload-script
 * injection, chokidar watching of source + template dirs, WebSocket reloads.
 */
export async function startDevServer(config: SiteConfig, port = 3000): Promise<DevServer> {
  const rebuild = (): void => {
    try {
      const result = buildSite(config);
      // eslint-disable-next-line no-console
      console.log(`[ssgen] built ${result.outputFiles.length} files`);
    } catch (err) {
      console.error('[ssgen] build failed:', err instanceof Error ? err.message : err);
    }
  };
  rebuild();

  const server = http.createServer((req, res) => {
    const file = resolveRequestPath(config.outputDir, req.url ?? '/');
    if (!file) {
      res.writeHead(404, { 'Content-Type': 'text/plain' });
      res.end('Not found');
      return;
    }
    const ext = path.extname(file).toLowerCase();
    const type = MIME[ext] ?? 'application/octet-stream';
    let body: Buffer | string = fs.readFileSync(file);
    if (ext === '.html') {
      body = injectReloadScript(body.toString('utf8'), port);
    }
    res.writeHead(200, { 'Content-Type': type });
    res.end(body);
  });

  const wss = new WebSocketServer({ server });
  const broadcast = (msg: string): void => {
    for (const client of wss.clients) {
      if (client.readyState === WebSocket.OPEN) client.send(msg);
    }
  };

  let timer: NodeJS.Timeout | null = null;
  const watcher = chokidar.watch([config.sourceDir, config.templateDir], {
    ignoreInitial: true,
  });
  watcher.on('all', () => {
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => {
      rebuild();
      broadcast('reload');
    }, 100);
  });

  await new Promise<void>((resolve) => server.listen(port, resolve));
  const address = server.address();
  const actualPort = typeof address === 'object' && address ? address.port : port;
  console.log(`[ssgen] dev server at http://localhost:${actualPort}`);

  return {
    port: actualPort,
    async close(): Promise<void> {
      await watcher.close();
      wss.close();
      await new Promise<void>((resolve, reject) =>
        server.close((err) => (err ? reject(err) : resolve())),
      );
    },
  };
}
