import { createReadStream } from 'node:fs';
import { access } from 'node:fs/promises';
import { createServer, type Server } from 'node:http';
import { extname, join, normalize, resolve } from 'node:path';
import chokidar, { type FSWatcher } from 'chokidar';
import { WebSocket, WebSocketServer } from 'ws';
import { buildSite, type BuildOptions } from '../generator.js';
import type { Plugin } from '../plugin.js';

const LIVE_RELOAD_SCRIPT = '<script>(() => { const socket = new WebSocket(`ws://${location.host}/__ssg_live_reload`); socket.onmessage = () => location.reload(); })();</script>';
const MIME_TYPES: Record<string, string> = { '.css': 'text/css; charset=utf-8', '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.json': 'application/json; charset=utf-8', '.svg': 'image/svg+xml' };

export interface DevServer {
  close(): Promise<void>;
  port: number;
}

function requestedFile(outputDir: string, requestUrl: string | undefined): string | undefined {
  const pathname = decodeURIComponent(new URL(requestUrl ?? '/', 'http://localhost').pathname);
  const relativePath = pathname === '/' ? 'index.html' : pathname.endsWith('/') ? `${pathname}index.html` : pathname.slice(1);
  const file = resolve(outputDir, normalize(relativePath));
  return file.startsWith(`${resolve(outputDir)}/`) || file === resolve(outputDir) ? file : undefined;
}

export class DevServerPlugin implements Plugin {
  private server?: Server;
  private watcher?: FSWatcher;
  private sockets?: WebSocketServer;
  private options: BuildOptions & { port?: number };
  private serverInfo?: DevServer;

  constructor(options: BuildOptions & { port?: number } = {}) {
    this.options = options;
  }

  async onStart(): Promise<void> {
    const outputDir = this.options.outputDir ?? './dist';
    const contentDir = this.options.contentDir ?? './content';
    const templatesDir = this.options.templatesDir ?? './templates';
    await buildSite({ ...this.options, contentDir, outputDir, templatesDir });
    this.server = createServer(async (request, response) => {
      const file = requestedFile(outputDir, request.url);
      if (!file) return void response.writeHead(403).end('Forbidden');
      try {
        await access(file);
        response.writeHead(200, { 'Content-Type': MIME_TYPES[extname(file).toLowerCase()] ?? 'application/octet-stream' });
        if (extname(file).toLowerCase() !== '.html') return void createReadStream(file).pipe(response);
        let html = '';
        for await (const chunk of createReadStream(file, 'utf8')) html += chunk;
        response.end(/<\/body\s*>/i.test(html) ? html.replace(/<\/body\s*>/i, `${LIVE_RELOAD_SCRIPT}</body>`) : `${html}${LIVE_RELOAD_SCRIPT}`);
      } catch {
        response.writeHead(404).end('Not found');
      }
    });
    this.sockets = new WebSocketServer({ noServer: true });
    this.server.on('upgrade', (request, socket, head) => {
      if (new URL(request.url ?? '/', 'http://localhost').pathname !== '/__ssg_live_reload') return socket.destroy();
      this.sockets?.handleUpgrade(request, socket, head, (client) => this.sockets?.emit('connection', client, request));
    });
    let rebuilding = false;
    let queued = false;
    const rebuild = async (): Promise<void> => {
      if (rebuilding) { queued = true; return; }
      rebuilding = true;
      try {
        await buildSite({ ...this.options, contentDir, outputDir, templatesDir });
        for (const client of this.sockets?.clients ?? []) if (client.readyState === WebSocket.OPEN) client.send('reload');
        process.stdout.write('Rebuilt site.\n');
      } catch (error: unknown) {
        process.stderr.write(`Build failed: ${error instanceof Error ? error.message : String(error)}\n`);
      } finally {
        rebuilding = false;
        if (queued) { queued = false; void rebuild(); }
      }
    };
    this.watcher = chokidar.watch([contentDir, templatesDir], { ignoreInitial: true });
    this.watcher.on('all', () => { void rebuild(); });
    await new Promise<void>((resolveListen, reject) => {
      this.server?.once('error', reject);
      this.server?.listen(this.options.port ?? 3000, 'localhost', () => {
        this.server?.off('error', reject);
        resolveListen();
      });
    });
    const address = this.server.address();
    if (!address || typeof address === 'string') throw new Error('Unable to determine server port');
    this.serverInfo = { port: address.port, close: () => this.close() };
  }

  get devServer(): DevServer {
    if (!this.serverInfo) throw new Error('Dev server has not started');
    return this.serverInfo;
  }

  async close(): Promise<void> {
    await this.watcher?.close();
    for (const client of this.sockets?.clients ?? []) client.close();
    if (this.server) await new Promise<void>((resolveClose, reject) => this.server?.close((error) => error ? reject(error) : resolveClose()));
    this.sockets?.close();
  }
}
