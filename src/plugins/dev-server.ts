import { createReadStream } from 'node:fs';
import { access, readFile } from 'node:fs/promises';
import { createServer, type Server } from 'node:http';
import path from 'node:path';
import chokidar, { type FSWatcher } from 'chokidar';
import { WebSocketServer } from 'ws';
import { buildSite, type BuildOptions } from '../generator.js';
import type { Plugin } from '../plugin.js';

export interface ServeOptions extends BuildOptions { port?: number; }
export interface DevelopmentServer { port: number; close(): Promise<void>; }

const reloadScript = '<script>(() => {\n'
  + '  const connect = () => {\n'
  + "    const socket = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}`);\n"
  + "    socket.addEventListener('message', () => location.reload());\n"
  + "    socket.addEventListener('close', () => setTimeout(connect, 1000));\n"
  + '  };\n  connect();\n})();</script>';

function contentType(file: string): string {
  if (file.endsWith('.html')) return 'text/html; charset=utf-8';
  if (file.endsWith('.css')) return 'text/css; charset=utf-8';
  if (file.endsWith('.js')) return 'text/javascript; charset=utf-8';
  if (file.endsWith('.json')) return 'application/json; charset=utf-8';
  if (file.endsWith('.svg')) return 'image/svg+xml';
  return 'application/octet-stream';
}

async function fileExists(file: string): Promise<boolean> {
  try { await access(file); return true; } catch { return false; }
}

export class DevServerPlugin implements Plugin {
  private server?: Server;
  private sockets?: WebSocketServer;
  private watcher?: FSWatcher;

  async start(options: ServeOptions = {}): Promise<DevelopmentServer> {
    const port = options.port ?? 3000;
    const contentDir = path.resolve(options.contentDir ?? 'content');
    const templatesDir = path.resolve(options.templatesDir ?? 'templates');
    const outputDir = path.resolve(options.outputDir ?? 'dist');
    const buildOptions = { contentDir, templatesDir, outputDir, incremental: true };
    await buildSite(buildOptions);
    this.server = createServer((request, response) => { void this.serve(request.url, outputDir, response); });
    this.sockets = new WebSocketServer({ server: this.server });
    this.watcher = chokidar.watch([contentDir, templatesDir], { ignoreInitial: true });
    let rebuilding = false;
    let rebuildQueued = false;
    const rebuild = async (): Promise<void> => {
      if (rebuilding) { rebuildQueued = true; return; }
      rebuilding = true;
      try {
        await buildSite(buildOptions);
        for (const socket of this.sockets!.clients) socket.send('reload');
        process.stdout.write('Rebuilt site.\n');
      } catch (error: unknown) {
        process.stderr.write(`Build failed: ${error instanceof Error ? error.message : String(error)}\n`);
      } finally {
        rebuilding = false;
        if (rebuildQueued) { rebuildQueued = false; await rebuild(); }
      }
    };
    this.watcher.on('all', () => { void rebuild(); });
    await new Promise<void>((resolve) => this.watcher!.once('ready', resolve));
    await new Promise<void>((resolve, reject) => {
      this.server!.once('error', reject);
      this.server!.listen(port, 'localhost', () => { this.server!.off('error', reject); resolve(); });
    });
    const address = this.server.address();
    if (!address || typeof address === 'string') throw new Error('Could not determine server port');
    process.stdout.write(`Serving ${outputDir} at http://localhost:${address.port}\n`);
    return { port: address.port, close: () => this.close() };
  }

  async onEnd(): Promise<void> {}

  private async serve(url: string | undefined, outputDir: string, response: import('node:http').ServerResponse): Promise<void> {
    const pathname = new URL(url ?? '/', 'http://localhost').pathname;
    const requestedFile = pathname === '/' ? 'index.html' : decodeURIComponent(pathname).replace(/^\/+/, '');
    const file = path.resolve(outputDir, requestedFile);
    if (!file.startsWith(`${outputDir}${path.sep}`) && file !== outputDir) { response.writeHead(403).end(); return; }
    if (!await fileExists(file)) { response.writeHead(404).end('Not found'); return; }
    response.setHeader('Content-Type', contentType(file));
    if (file.endsWith('.html')) {
      const html = await readFile(file, 'utf8');
      response.end(/<\/body\s*>/i.test(html) ? html.replace(/<\/body\s*>/i, `${reloadScript}</body>`) : `${html}${reloadScript}`);
    } else createReadStream(file).pipe(response);
  }

  private async close(): Promise<void> {
    await this.watcher?.close();
    for (const socket of this.sockets?.clients ?? []) socket.terminate();
    if (this.sockets) await new Promise<void>((resolve, reject) => this.sockets!.close((error) => error ? reject(error) : resolve()));
    if (this.server) await new Promise<void>((resolve, reject) => this.server!.close((error) => error ? reject(error) : resolve()));
  }
}
