import fs from 'fs';
import http from 'http';
import net from 'net';
import path from 'path';
import { WebSocketServer, WebSocket } from 'ws';
import { watch, FSWatcher } from 'chokidar';
import { build } from './ssg';
import type { ServeOptions } from './types';

export const LIVE_RELOAD_PATH = '/__ssg_livereload';

const RELOAD_MESSAGE = 'reload';
const DEFAULT_HOST = 'localhost';
const DEFAULT_PORT = 3000;
const REBUILD_DEBOUNCE_MS = 100;

const HTML_EXTENSIONS = ['.html', '.htm'];

const LIVE_RELOAD_SCRIPT = `<script>(function(){try{var s=new WebSocket((location.protocol==='https:'?'wss://':'ws://')+location.host+'${LIVE_RELOAD_PATH}');s.onmessage=function(){location.reload();};}catch(e){}})();</script>`;

/**
 * Inject the live-reload WebSocket client script into an HTML document.
 * The script is inserted just before the closing `</body>` tag when present,
 * otherwise appended to the end of the document.
 */
export function injectLiveReloadScript(html: string): string {
  const closeBody = html.lastIndexOf('</body>');
  if (closeBody !== -1) {
    return html.slice(0, closeBody) + LIVE_RELOAD_SCRIPT + html.slice(closeBody);
  }
  return html + LIVE_RELOAD_SCRIPT;
}

export interface DevServerHandle {
  url: string;
  port: number;
  rebuild(): void;
  close(): Promise<void>;
}

/**
 * A live-reload development server that serves a freshly built site from the
 * output directory, watches the content and template directories with
 * chokidar, rebuilds on change, and pushes a reload message to connected
 * browsers over a WebSocket.
 */
export function startDevServer(options: ServeOptions): Promise<DevServerHandle> {
  return new Promise((resolve, reject) => {
    const port = options.port ?? DEFAULT_PORT;
    const host = options.host ?? DEFAULT_HOST;
    const outputDir = path.resolve(options.outputDir);

    let closed = false;
    let rebuildTimer: NodeJS.Timeout | null = null;
    let watcher: FSWatcher | null = null;
    let wss: WebSocketServer | null = null;
    const sockets = new Set<net.Socket>();

    const server = http.createServer((req, res) => {
      const urlPath = (req.url ?? '/').split('?')[0];

      if (urlPath === LIVE_RELOAD_PATH) {
        res.writeHead(404);
        res.end();
        return;
      }

      let relative: string;
      try {
        relative = decodeURIComponent(urlPath === '/' ? '/index.html' : urlPath);
      } catch {
        res.writeHead(400);
        res.end('Bad Request');
        return;
      }
      const filePath = path.resolve(outputDir, `.${relative}`);

      if (!filePath.startsWith(outputDir + path.sep) && filePath !== outputDir) {
        res.writeHead(403);
        res.end('Forbidden');
        return;
      }

      let content: Buffer;
      try {
        content = fs.readFileSync(filePath);
      } catch {
        res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
        res.end('Not Found');
        return;
      }

      const ext = path.extname(filePath).toLowerCase();
      const isHtml = HTML_EXTENSIONS.includes(ext);
      const headers: Record<string, string> = isHtml
        ? { 'Content-Type': 'text/html; charset=utf-8' }
        : {};

      let body: Buffer = content;
      if (isHtml) {
        body = Buffer.from(injectLiveReloadScript(content.toString('utf-8')), 'utf-8');
      }
      res.writeHead(200, headers);
      res.end(body);
    });

    server.on('connection', (socket) => {
      sockets.add(socket);
      socket.on('close', () => sockets.delete(socket));
    });

    const broadcast = () => {
      if (!wss) return;
      for (const client of wss.clients) {
        if (client.readyState === WebSocket.OPEN) {
          client.send(RELOAD_MESSAGE);
        }
      }
    };

    const rebuild = () => {
      try {
        build({
          contentDir: options.contentDir,
          outputDir: options.outputDir,
          templatesDir: options.templatesDir,
        });
        console.log(`[ssg] rebuilt site in ${options.outputDir}`);
      } catch (err) {
        console.error(`[ssg] build failed: ${(err as Error).message}`);
        return;
      }
      broadcast();
    };

    const scheduleRebuild = () => {
      if (closed) return;
      if (rebuildTimer) clearTimeout(rebuildTimer);
      rebuildTimer = setTimeout(() => {
        rebuildTimer = null;
        rebuild();
      }, REBUILD_DEBOUNCE_MS);
    };

    server.once('error', (err) => {
      reject(err);
    });

    server.listen(port, host, () => {
      try {
        wss = new WebSocketServer({ server, path: LIVE_RELOAD_PATH });
      } catch (err) {
        server.close();
        reject(err as Error);
        return;
      }

      const watchedPaths: string[] = [path.resolve(options.contentDir)];
      if (options.templatesDir) {
        watchedPaths.push(path.resolve(options.templatesDir));
      }

      try {
        rebuild();
      } catch {
        // The initial build may fail if the content directory does not exist
        // yet; keep serving and let chokidar trigger a rebuild once it appears.
      }

      watcher = watch(watchedPaths, {
        ignoreInitial: true,
      });

      watcher.on('all', () => {
        scheduleRebuild();
      });

      watcher.on('error', (err) => {
        console.error(`[ssg] watcher error: ${(err as Error).message ?? String(err)}`);
      });

      const address = server.address();
      const boundPort = typeof address === 'object' && address !== null ? address.port : port;

      const handle: DevServerHandle = {
        url: `http://${host}:${boundPort}`,
        port: boundPort,
        rebuild,
        close: async () => {
          if (closed) return;
          closed = true;
          if (rebuildTimer) clearTimeout(rebuildTimer);
          if (watcher) await watcher.close();
          // Let the watcher's underlying fs.watch handles settle before tearing
          // down the HTTP server; inotify cleanup is not fully synchronous.
          await new Promise<void>((done) => setImmediate(done));
          if (wss) {
            for (const client of wss.clients) client.terminate();
            wss.close();
          }
          await new Promise<void>((done) => {
            server.close(() => done());
            server.closeAllConnections();
            for (const socket of sockets) socket.destroy();
          });
        },
      };

      // Wait for the watcher's initial scan to finish before handing the server
      // back, so the watcher is fully initialized (and closable) immediately.
      const readyWatcher = watcher;
      const waitForReady = new Promise<void>((readyResolve) => {
        const readyTimer = setTimeout(readyResolve, 1000);
        readyWatcher.once('ready', () => {
          clearTimeout(readyTimer);
          readyResolve();
        });
      });

      waitForReady.then(() => resolve(handle));
    });
  });
}
