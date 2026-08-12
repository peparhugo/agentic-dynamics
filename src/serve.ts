import fs from 'fs';
import http from 'http';
import path from 'path';
import chokidar from 'chokidar';
import { WebSocket, WebSocketServer } from 'ws';
import { build } from './ssg';
import { DevServerPlugin, WS_PATH } from './plugins/dev-server';

export { LIVE_RELOAD_SCRIPT_ID, WS_PATH, liveReloadScript, injectLiveReload } from './plugins/dev-server';

/** Default port for the development server. */
export const DEFAULT_PORT = 3000;

const devServerPlugin = new DevServerPlugin();

export interface ServeOptions {
  content: string;
  output: string;
  templates: string;
  port: number;
}

export interface DevServer {
  /** Underlying HTTP server. */
  server: http.Server;
  /** WebSocket server attached to the HTTP server. */
  wss: WebSocketServer;
  /** chokidar watcher over content/ and templates/. */
  watcher: chokidar.FSWatcher;
  /** Resolves once the initial file scan has completed. */
  ready: Promise<void>;
  /** Number of rebuilds performed so far. */
  getRebuildCount(): number;
  /** Start listening and resolve with the actual port in use. */
  listen(): Promise<number>;
  /** Close the watcher, WebSocket server, and HTTP server. */
  stop(): Promise<void>;
}

const MIME_TYPES: Record<string, string> = {
  '.html': 'text/html; charset=utf-8',
  '.htm': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
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
  '.ttf': 'font/ttf',
  '.eot': 'application/vnd.ms-fontobject',
  '.txt': 'text/plain; charset=utf-8',
  '.xml': 'text/xml; charset=utf-8',
  '.map': 'application/json; charset=utf-8',
};

/** Send a message to every connected client, returning how many got it. */
export function broadcast(wss: WebSocketServer, message: string): number {
  let count = 0;
  for (const client of wss.clients) {
    if (client.readyState === WebSocket.OPEN) {
      client.send(message);
      count += 1;
    }
  }
  return count;
}

/** Send a reload message to every connected client. */
export function broadcastReload(wss: WebSocketServer): number {
  return broadcast(wss, 'reload');
}

/** Resolve a request path to an absolute file inside the output directory. */
export function resolveFilePath(url: string | undefined, outputDir: string): string | null {
  const pathname = decodeURIComponent(new URL(url ?? '/', 'http://localhost').pathname);
  let relPath = pathname === '/' ? '/index.html' : pathname;
  if (relPath.endsWith('/')) relPath += 'index.html';

  const root = path.resolve(outputDir);
  const filePath = path.normalize(path.join(root, relPath));
  if (filePath !== root && !filePath.startsWith(root + path.sep)) {
    return null;
  }
  return filePath;
}

function serveFile(req: http.IncomingMessage, res: http.ServerResponse, options: ServeOptions, port: number): void {
  const filePath = resolveFilePath(req.url, options.output);
  if (filePath === null) {
    res.writeHead(403, { 'Content-Type': 'text/plain' });
    res.end('Forbidden');
    return;
  }

  if (!fs.existsSync(filePath) || !fs.statSync(filePath).isFile()) {
    res.writeHead(404, { 'Content-Type': 'text/plain' });
    res.end('Not Found');
    return;
  }

  const ext = path.extname(filePath).toLowerCase();
  const contentType = MIME_TYPES[ext] ?? 'application/octet-stream';
  res.writeHead(200, { 'Content-Type': contentType });

  if (ext === '.html' || ext === '.htm') {
    const html = fs.readFileSync(filePath, 'utf8');
    res.end(devServerPlugin.injectLiveReload(html, port));
  } else {
    fs.createReadStream(filePath).pipe(res);
  }
}

/**
 * Build the site and start serving it from the output directory with
 * live-reload enabled. Content/ and templates/ are watched and any change
 * triggers a rebuild followed by a reload broadcast to connected browsers.
 */
export function createDevServer(options: ServeOptions): DevServer {
  build(options.content, options.output, options.templates);

  const wss = new WebSocketServer({ noServer: true });
  const outputDir = path.resolve(options.output);
  let actualPort = options.port;

  const server = http.createServer((req, res) => {
    serveFile(req, res, options, actualPort);
  });

  server.on('upgrade', (req, socket, head) => {
    const pathname = new URL(req.url ?? '/', 'http://localhost').pathname;
    if (pathname === WS_PATH) {
      wss.handleUpgrade(req, socket, head, (ws) => {
        wss.emit('connection', ws, req);
      });
    } else {
      socket.destroy();
    }
  });

  const watcher = chokidar.watch([options.content, options.templates], {
    ignoreInitial: true,
    ignored: (watchedPath: string) => {
      const abs = path.resolve(watchedPath);
      return abs === outputDir || abs.startsWith(outputDir + path.sep);
    },
  });

  const ready = new Promise<void>((resolve) => {
    watcher.once('ready', () => resolve());
  });

  let rebuilding = false;
  let pending = false;
  let rebuildCount = 0;

  const rebuild = (): void => {
    if (rebuilding) {
      pending = true;
      return;
    }
    rebuilding = true;
    try {
      build(options.content, options.output, options.templates);
      rebuildCount += 1;
      broadcast(wss, 'reload');
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      broadcast(wss, `error:${message}`);
    } finally {
      rebuilding = false;
      if (pending) {
        pending = false;
        rebuild();
      }
    }
  };

  watcher.on('all', rebuild);

  return {
    server,
    wss,
    watcher,
    ready,
    getRebuildCount: () => rebuildCount,
    listen: () =>
      new Promise<number>((resolve) => {
        server.listen(options.port, () => {
          const addr = server.address();
          actualPort = typeof addr === 'object' && addr !== null ? addr.port : options.port;
          resolve(actualPort);
        });
      }),
    stop: async () => {
      await watcher.close();
      for (const client of wss.clients) client.terminate();
      await new Promise<void>((resolve) => wss.close(() => resolve()));
      const closed = new Promise<void>((resolve) => server.once('close', () => resolve()));
      server.close();
      server.closeAllConnections();
      await closed;
    },
  };
}

/**
 * Start the dev server and keep the process alive. Resolves once the HTTP
 * server has closed.
 */
export async function startServe(options: ServeOptions): Promise<void> {
  const dev = createDevServer(options);
  const port = await dev.listen();
  process.stdout.write(
    `SSG dev server running at http://localhost:${port}\n` +
      `Watching ${options.content} and ${options.templates}\n`
  );
  await new Promise<void>((resolve) => {
    dev.server.once('close', () => resolve());
  });
}
