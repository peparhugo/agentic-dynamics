import { createServer, type Server } from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import path from 'node:path';
import { WebSocket, WebSocketServer } from 'ws';
import chokidar, { type FSWatcher } from 'chokidar';
import { buildSite } from '../generator';
import type { Plugin, PluginContext } from '../plugin';

export const DEFAULT_PORT = 3000;
export const WS_PATH = '/__ssg_reload__';
export const RELOAD_MESSAGE = 'reload';

export interface ServeOptions {
  contentDir: string;
  outputDir: string;
  templatesDir: string;
  port: number;
  plugins?: Plugin[];
  configPath?: string;
}

export interface ServeHandle {
  server: Server;
  wss: WebSocketServer;
  watcher: FSWatcher;
  stop: () => Promise<void>;
}

const MIME_TYPES: Record<string, string> = {
  '.html': 'text/html; charset=utf-8',
  '.htm': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.map': 'application/json; charset=utf-8',
  '.txt': 'text/plain; charset=utf-8',
  '.xml': 'application/xml; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.svg': 'image/svg+xml',
  '.webp': 'image/webp',
  '.ico': 'image/x-icon',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
  '.ttf': 'font/ttf',
  '.mp4': 'video/mp4',
  '.webm': 'video/webm',
  '.pdf': 'application/pdf',
};

export function contentType(filePath: string): string {
  return MIME_TYPES[path.extname(filePath).toLowerCase()] ?? 'application/octet-stream';
}

export function liveReloadScript(port: number): string {
  return `<script data-ssg-live-reload>
(function () {
  var protocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
  var socket = new WebSocket(protocol + window.location.host + '${WS_PATH}');
  socket.onmessage = function (event) {
    if (event.data === '${RELOAD_MESSAGE}') {
      window.location.reload();
    }
  };
})();
</script>`;
}

export function injectLiveReloadScript(html: string, port: number): string {
  const script = liveReloadScript(port);
  if (html.includes('</body>')) {
    return html.replace('</body>', `${script}\n</body>`);
  }
  if (html.includes('</head>')) {
    return html.replace('</head>', `${script}\n</head>`);
  }
  return `${html}\n${script}`;
}

export async function resolveFile(outputDir: string, pathname: string): Promise<string | null> {
  const root = path.resolve(outputDir);
  const candidates: string[] = [];
  const normalized = path.posix.normalize(pathname).replace(/^\/+/, '');

  if (normalized === '' || normalized === '.') {
    candidates.push('index.html');
  } else {
    candidates.push(normalized);
    if (!path.posix.extname(normalized)) {
      candidates.push(`${normalized}.html`);
      candidates.push(path.posix.join(normalized, 'index.html'));
    }
  }

  for (const candidate of candidates) {
    const full = path.resolve(root, candidate);
    if (full !== root && !full.startsWith(root + path.sep)) {
      continue;
    }
    try {
      const st = await stat(full);
      if (st.isFile()) {
        return full;
      }
    } catch {
      // continue looking
    }
  }

  return null;
}

async function startDevServer(options: ServeOptions): Promise<ServeHandle> {
  const { contentDir, outputDir, templatesDir, port, plugins, configPath } = options;

  await buildSite(contentDir, outputDir, { templatesDir, plugins, configPath, incremental: true });

  const wss = new WebSocketServer({ noServer: true });
  const server = createServer(async (req, res) => {
    if (req.method !== 'GET' && req.method !== 'HEAD') {
      res.writeHead(405, { 'Content-Type': 'text/plain; charset=utf-8' });
      res.end('Method Not Allowed');
      return;
    }

    let pathname: string;
    try {
      pathname = decodeURIComponent(new URL(req.url ?? '/', 'http://localhost').pathname);
    } catch {
      res.writeHead(400, { 'Content-Type': 'text/plain; charset=utf-8' });
      res.end('Bad Request');
      return;
    }

    const file = await resolveFile(outputDir, pathname);
    if (file === null) {
      res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
      res.end('Not Found');
      return;
    }

    let body = await readFile(file);
    const isHtml = path.extname(file).toLowerCase() === '.html';
    if (isHtml) {
      body = Buffer.from(injectLiveReloadScript(body.toString('utf8'), port), 'utf8');
    }

    res.writeHead(200, {
      'Content-Type': contentType(file),
      'Cache-Control': 'no-cache',
    });
    if (req.method === 'HEAD') {
      res.end();
    } else {
      res.end(body);
    }
  });

  server.on('upgrade', (req, socket, head) => {
    let url: URL;
    try {
      url = new URL(req.url ?? '/', 'http://localhost');
    } catch {
      socket.destroy();
      return;
    }
    if (url.pathname !== WS_PATH) {
      socket.destroy();
      return;
    }
    wss.handleUpgrade(req, socket, head, (ws) => {
      wss.emit('connection', ws, req);
    });
  });

  function broadcastReload(): void {
    for (const client of wss.clients) {
      if (client.readyState === WebSocket.OPEN) {
        client.send(RELOAD_MESSAGE);
      }
    }
  }

  const watcher = chokidar.watch([contentDir, templatesDir], { ignoreInitial: true });

  await new Promise<void>((resolve) => {
    watcher.once('ready', () => resolve());
  });
  await new Promise<void>((resolve) => setTimeout(resolve, 100));

  let timer: NodeJS.Timeout | undefined;
  const scheduleRebuild = (): void => {
    if (timer) {
      clearTimeout(timer);
    }
    timer = setTimeout(async () => {
      try {
        await buildSite(contentDir, outputDir, { templatesDir, plugins, configPath, incremental: true });
        console.log('Rebuilt site');
        broadcastReload();
      } catch (err) {
        console.error(`Build failed: ${err instanceof Error ? err.message : String(err)}`);
      }
    }, 80);
  };
  watcher.on('all', scheduleRebuild);

  await new Promise<void>((resolve, reject) => {
    const onError = (err: Error): void => {
      server.off('listening', onListening);
      reject(err);
    };
    const onListening = (): void => {
      server.off('error', onError);
      resolve();
    };
    server.once('error', onError);
    server.once('listening', onListening);
    server.listen(port);
  });

  let stopped = false;
  async function stop(): Promise<void> {
    if (stopped) return;
    stopped = true;
    if (timer) {
      clearTimeout(timer);
      timer = undefined;
    }
    await watcher.close();
    for (const client of wss.clients) {
      client.terminate();
    }
    wss.close();
    await new Promise<void>((resolve) => server.close(() => resolve()));
  }

  return { server, wss, watcher, stop };
}

export class DevServerPlugin implements Plugin {
  readonly name = 'dev-server';

  private readonly options: ServeOptions;
  private handle: ServeHandle | undefined;

  constructor(options: ServeOptions) {
    this.options = options;
  }

  async onStart(context: PluginContext): Promise<void> {
    await this.start();
  }

  async onEnd(context: PluginContext): Promise<void> {
    await this.stop();
  }

  async start(): Promise<void> {
    if (this.handle) {
      return;
    }
    this.handle = await startDevServer(this.options);
  }

  async stop(): Promise<void> {
    if (this.handle) {
      const handle = this.handle;
      this.handle = undefined;
      await handle.stop();
    }
  }

  getServer(): Server | null {
    return this.handle?.server ?? null;
  }

  getWss(): WebSocketServer | null {
    return this.handle?.wss ?? null;
  }

  getWatcher(): FSWatcher | null {
    return this.handle?.watcher ?? null;
  }

  toHandle(): ServeHandle {
    if (!this.handle) {
      throw new Error('Dev server has not been started');
    }
    return this.handle;
  }
}
