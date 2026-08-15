import { createServer, Server, IncomingMessage, ServerResponse } from 'http';
import type { AddressInfo } from 'net';
import { promises as fs } from 'fs';
import path from 'path';
import chokidar, { FSWatcher } from 'chokidar';
import { WebSocketServer, WebSocket } from 'ws';
import { build } from './build';

export interface ServeOptions {
  content: string;
  output: string;
  templates?: string;
  port?: number;
}

export interface DevServer {
  port: number;
  reload(): void;
  close(): Promise<void>;
}

const MIME_TYPES: Record<string, string> = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.txt': 'text/plain; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.ico': 'image/x-icon',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
};

export function liveReloadScript(): string {
  return [
    '<script data-ssg-live-reload>',
    '(function(){',
    '  var ws=new WebSocket("ws://"+location.host);',
    '  ws.onmessage=function(e){ if(e.data==="reload"){ location.reload(); } };',
    '})();',
    '</script>',
  ].join('\n');
}

export function injectLiveReload(html: string): string {
  const script = liveReloadScript();
  if (/<\/body>/i.test(html)) {
    return html.replace(/<\/body>/i, `${script}\n</body>`);
  }
  return `${html}\n${script}\n`;
}

export async function serve(options: ServeOptions): Promise<DevServer> {
  const contentDir = path.resolve(options.content);
  const outputDir = path.resolve(options.output);
  const templatesDir = options.templates ?? './templates';
  const requestedPort = options.port ?? 3000;

  const server = createServer((req, res) => {
    void handleRequest(req, res, outputDir);
  });

  const wss = new WebSocketServer({ server });

  let building = false;
  let queued = false;

  function broadcastReload(): void {
    for (const client of wss.clients) {
      if (client.readyState === WebSocket.OPEN) {
        client.send('reload');
      }
    }
  }

  async function rebuild(): Promise<void> {
    if (building) {
      queued = true;
      return;
    }
    building = true;
    try {
      await build({ content: contentDir, output: outputDir, templates: templatesDir });
      broadcastReload();
    } finally {
      building = false;
      if (queued) {
        queued = false;
        await rebuild();
      }
    }
  }

  const watcher = chokidar.watch([contentDir, templatesDir], {
    ignoreInitial: true,
  });

  let debounceTimer: NodeJS.Timeout | null = null;
  const scheduleRebuild = (): void => {
    if (debounceTimer) {
      clearTimeout(debounceTimer);
    }
    debounceTimer = setTimeout(() => {
      debounceTimer = null;
      void rebuild();
    }, 50);
  };

  watcher.on('add', scheduleRebuild);
  watcher.on('change', scheduleRebuild);
  watcher.on('unlink', scheduleRebuild);
  watcher.on('addDir', scheduleRebuild);
  watcher.on('unlinkDir', scheduleRebuild);

  await rebuild();

  await new Promise<void>((resolve, reject) => {
    server.once('error', reject);
    server.listen(requestedPort, () => {
      server.removeListener('error', reject);
      resolve();
    });
  });

  const address = server.address() as AddressInfo;
  const port = address.port;

  return {
    port,
    reload: broadcastReload,
    async close(): Promise<void> {
      if (debounceTimer) {
        clearTimeout(debounceTimer);
        debounceTimer = null;
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
    },
  };
}

async function handleRequest(
  req: IncomingMessage,
  res: ServerResponse,
  outputDir: string
): Promise<void> {
  const rawUrl = (req.url ?? '/').split('?')[0];
  const urlPath = decodeURIComponent(rawUrl);

  let filePath: string;
  if (urlPath === '/' || urlPath === '') {
    filePath = path.join(outputDir, 'index.html');
  } else {
    filePath = path.resolve(outputDir, urlPath.slice(1));
  }

  const relative = path.relative(outputDir, filePath);
  if (relative.startsWith('..') || path.isAbsolute(relative)) {
    res.writeHead(403, { 'Content-Type': 'text/plain; charset=utf-8' });
    res.end('Forbidden');
    return;
  }

  try {
    const stat = await fs.stat(filePath);
    if (stat.isDirectory()) {
      filePath = path.join(filePath, 'index.html');
    }
  } catch {
    res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
    res.end('Not found');
    return;
  }

  let content: Buffer;
  try {
    content = await fs.readFile(filePath);
  } catch {
    res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
    res.end('Not found');
    return;
  }

  const ext = path.extname(filePath).toLowerCase();
  const contentType = MIME_TYPES[ext] ?? 'application/octet-stream';

  if (ext === '.html') {
    content = Buffer.from(injectLiveReload(content.toString('utf8')), 'utf8');
  }

  res.writeHead(200, { 'Content-Type': contentType });
  res.end(content);
}
