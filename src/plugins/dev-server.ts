/**
 * Built-in plugin that provides the live-reload development server.
 *
 * The plugin implements both the SSG `Plugin` lifecycle (its `afterBuild`
 * hook notifies connected browsers to reload) and the `DevServer` API so it
 * can be driven directly by `startDevServer`.
 */

import fs from 'fs';
import http from 'http';
import path from 'path';

import chokidar from 'chokidar';
import type { FSWatcher } from 'chokidar';
import WebSocket from 'ws';

import { buildSite } from '../site';
import type { Plugin, PluginContext } from '../plugin';
import type { Page } from '../types';

/** Default port used by the development server. */
export const DEFAULT_PORT = 3000;
/** WebSocket path browsers connect to for live reload notifications. */
export const RELOAD_PATH = '/__ssg_reload';
/** Debounce window (ms) used before rebuilding after a file change. */
export const REBUILD_DELAY_MS = 100;

/** Options controlling the development server. */
export interface ServeOptions {
  /** Directory containing Markdown content files. */
  contentDir: string;
  /** Directory where generated HTML files are written and served from. */
  outputDir: string;
  /** Directory containing templates, layouts and partials. */
  templatesDir: string;
  /** Port to listen on (default: {@link DEFAULT_PORT}). */
  port?: number;
}

/** A running development server instance. */
export interface DevServer {
  /** The underlying HTTP server. */
  server: http.Server;
  /** The WebSocket server used for live reload messages. */
  wss: WebSocket.WebSocketServer;
  /** The chokidar watcher watching content and templates. */
  watcher: FSWatcher;
  /** The directory being served. */
  outputDir: string;
  /** The port the server is actually bound to. */
  port: number;
  /** Rebuild the site immediately and return the built pages. */
  rebuild(): Page[];
  /** Send a reload notification to every connected browser. */
  broadcast(): void;
  /** Stop the server, watcher and all WebSocket connections. */
  close(): Promise<void>;
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
  '.md': 'text/markdown; charset=utf-8',
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
  '.otf': 'font/otf',
  '.eot': 'application/vnd.ms-fontobject',
};

/**
 * Inject the live-reload client script into an HTML document. The script
 * opens a WebSocket to the current host and reloads the page whenever a
 * message is received.
 */
export function injectLiveReloadScript(html: string): string {
  const script = `<script>
(function () {
  var scheme = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
  function connect() {
    var ws = new WebSocket(scheme + window.location.host + '${RELOAD_PATH}');
    ws.onopen = function () {};
    ws.onmessage = function (event) {
      if (event.data) { window.location.reload(); }
    };
    ws.onclose = function () { setTimeout(connect, 1000); };
  }
  connect();
})();
</script>`;

  const closingTag = '</body>';
  const closingIndex = html.toLowerCase().lastIndexOf(closingTag);
  if (closingIndex === -1) {
    return `${html}\n${script}`;
  }
  return `${html.slice(0, closingIndex)}${script}\n${closingTag}${html.slice(
    closingIndex + closingTag.length,
  )}`;
}

/** Notify every connected browser to reload. */
function notifyClients(wss: WebSocket.WebSocketServer): void {
  const data = JSON.stringify({ type: 'reload' });
  for (const client of wss.clients) {
    if (client.readyState === WebSocket.OPEN) {
      client.send(data);
    }
  }
}

/** Serve a single file from the output directory over the HTTP response. */
function sendFile(res: http.ServerResponse, filePath: string): void {
  fs.readFile(filePath, (err, data) => {
    if (err) {
      res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
      res.end('Not Found');
      return;
    }
    const ext = path.extname(filePath).toLowerCase();
    const contentType = MIME_TYPES[ext] ?? 'application/octet-stream';
    if (ext === '.html' || ext === '.htm') {
      res.writeHead(200, { 'Content-Type': contentType });
      res.end(injectLiveReloadScript(data.toString('utf8')));
    } else {
      res.writeHead(200, { 'Content-Type': contentType });
      res.end(data);
    }
  });
}

/** Resolve a request URL into a safe path inside the output directory. */
function resolveRequestPath(outputDir: string, rawPath: string): string | null {
  let pathname: string;
  try {
    pathname = decodeURIComponent(rawPath);
  } catch {
    return null;
  }
  if (pathname === '/') {
    pathname = '/index.html';
  }
  const resolved = path.resolve(outputDir, `.${pathname}`);
  const relative = path.relative(outputDir, resolved);
  if (relative.startsWith('..') || path.isAbsolute(relative)) {
    return null;
  }
  return resolved;
}

/** Plugin name used to identify the dev server plugin. */
export const DEV_SERVER_PLUGIN_NAME = 'dev-server';

/**
 * The live-reload development server as an SSG plugin. Registered into the
 * plugin pipeline, its `afterBuild` hook broadcasts a reload message to every
 * connected browser after each rebuild.
 */
export class DevServerPlugin implements Plugin, DevServer {
  readonly name = DEV_SERVER_PLUGIN_NAME;

  private options: ServeOptions;

  server!: http.Server;
  wss!: WebSocket.WebSocketServer;
  watcher!: FSWatcher;
  outputDir!: string;
  port!: number;

  private timer: ReturnType<typeof setTimeout> | null = null;

  constructor(options?: Partial<ServeOptions>) {
    this.options = {
      contentDir: options?.contentDir ?? 'content',
      outputDir: options?.outputDir ?? 'dist',
      templatesDir: options?.templatesDir ?? 'templates',
      port: options?.port ?? DEFAULT_PORT,
    };
  }

  /**
   * Build the site once and start serving the output directory with live
   * reload. Resolves once the server is listening.
   */
  async start(): Promise<void> {
    const { contentDir, outputDir, templatesDir } = this.options;

    this.rebuild();

    const server = http.createServer((req, res) => {
      const target = resolveRequestPath(outputDir, req.url ?? '/');
      if (!target) {
        res.writeHead(403, { 'Content-Type': 'text/plain; charset=utf-8' });
        res.end('Forbidden');
        return;
      }
      fs.stat(target, (statErr, stats) => {
        if (statErr || !stats.isFile()) {
          res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
          res.end('Not Found');
          return;
        }
        sendFile(res, target);
      });
    });

    const wss = new WebSocket.WebSocketServer({
      server,
      path: RELOAD_PATH,
    });

    const watchTargets: string[] = [contentDir];
    if (fs.existsSync(templatesDir)) {
      watchTargets.push(templatesDir);
    }

    const watcher = chokidar.watch(watchTargets, { ignoreInitial: true });

    watcher.on('all', () => {
      if (this.timer) {
        clearTimeout(this.timer);
      }
      this.timer = setTimeout(() => {
        this.timer = null;
        this.rebuild();
        this.broadcast();
      }, REBUILD_DELAY_MS);
    });

    await new Promise<void>((resolve, reject) => {
      server.once('error', reject);
      server.listen(this.options.port, () => {
        server.removeListener('error', reject);
        resolve();
      });
    });

    const address = server.address();
    const boundPort =
      address !== null && typeof address === 'object'
        ? address.port
        : this.options.port ?? DEFAULT_PORT;

    this.server = server;
    this.wss = wss;
    this.watcher = watcher;
    this.outputDir = outputDir;
    this.port = boundPort;
  }

  /** Rebuild the site immediately and return the built pages. */
  rebuild(): Page[] {
    const { contentDir, outputDir, templatesDir } = this.options;
    try {
      return buildSite({ contentDir, outputDir, templatesDir, plugins: [this] });
    } catch (error) {
      console.error('[ssg] Build failed:', error);
      return [];
    }
  }

  /** Send a reload notification to every connected browser. */
  broadcast(): void {
    if (!this.wss) return;
    notifyClients(this.wss);
  }

  /** Plugin hook: notify browsers to reload after every build. */
  afterBuild(_context: PluginContext): void {
    this.broadcast();
  }

  /** Stop the server, watcher and all WebSocket connections. */
  async close(): Promise<void> {
    if (this.timer) {
      clearTimeout(this.timer);
      this.timer = null;
    }
    if (this.watcher) {
      await this.watcher.close();
    }
    if (this.wss) {
      for (const client of this.wss.clients) {
        client.terminate();
      }
      this.wss.close();
    }
    if (this.server) {
      await new Promise<void>((resolve) => {
        this.server.close(() => resolve());
        this.server.closeAllConnections?.();
      });
    }
  }
}

/**
 * Build the site once and start a live-reload dev server that serves the
 * output directory. Returns once the server is listening.
 */
export async function startDevServer(options: ServeOptions): Promise<DevServer> {
  const plugin = new DevServerPlugin(options);
  await plugin.start();
  return plugin;
}
