import { createReadStream, existsSync } from 'node:fs';
import { readFile, stat } from 'node:fs/promises';
import { createServer } from 'node:http';
import { extname, resolve, sep } from 'node:path';
import chokidar, { type FSWatcher } from 'chokidar';
import { WebSocketServer } from 'ws';
import { createEngine } from '../engine';
import type { BuildOptions } from '../generator';
import type { Plugin } from './plugin';

export interface ServeOptions extends BuildOptions { port?: number; }
export interface DevelopmentServer { port: number; close(): Promise<void>; }

const reloadClient = `<script>(() => {
  const socket = new WebSocket((location.protocol === 'https:' ? 'wss' : 'ws') + '://' + location.host);
  socket.addEventListener('message', event => { if (event.data === 'reload') location.reload(); });
})();</script>`;

function servedPath(outputDir: string, requestUrl: string): string | undefined {
  const pathname = decodeURIComponent(new URL(requestUrl, 'http://localhost').pathname);
  const root = resolve(outputDir);
  const file = resolve(root, pathname === '/' ? 'index.html' : pathname.replace(/^\/+/, ''));
  return file === root || file.startsWith(`${root}${sep}`) ? file : undefined;
}

export class DevServerPlugin implements Plugin {
  async start(options: ServeOptions = {}): Promise<DevelopmentServer> {
    const buildOptions: BuildOptions = { contentDir: options.contentDir, templateDir: options.templateDir, outputDir: options.outputDir };
    const outputDir = options.outputDir ?? './dist';
    const engine = await createEngine();
    await engine.build(buildOptions);
    const server = createServer((request, response) => {
      void this.sendFile(outputDir, request.url ?? '/', response).catch(() => response.writeHead(500).end('Server error'));
    });
    const sockets = new WebSocketServer({ server });
    let rebuilding = false;
    let rebuildQueued = false;
    const rebuild = async (): Promise<void> => {
      if (rebuilding) { rebuildQueued = true; return; }
      rebuilding = true;
      try {
        await engine.build(buildOptions);
        for (const client of sockets.clients) client.send('reload');
        console.log('Rebuilt site.');
      } catch (error) { console.error(error instanceof Error ? error.message : error); }
      finally {
        rebuilding = false;
        if (rebuildQueued) { rebuildQueued = false; void rebuild(); }
      }
    };
    const watcher: FSWatcher = chokidar.watch([options.contentDir ?? './content', options.templateDir ?? './templates'], { ignoreInitial: true });
    watcher.on('all', () => void rebuild());
    await new Promise<void>((listening) => server.listen(options.port ?? 3000, 'localhost', listening));
    const address = server.address();
    const port = typeof address === 'object' && address !== null ? address.port : options.port ?? 3000;
    console.log(`Serving site at http://localhost:${port}`);
    return { port, close: async () => {
      await watcher.close();
      for (const client of sockets.clients) client.terminate();
      sockets.close();
      await new Promise<void>((close, reject) => server.close((error) => error ? reject(error) : close()));
    } };
  }

  private async sendFile(outputDir: string, requestUrl: string, response: import('node:http').ServerResponse): Promise<void> {
    const file = servedPath(outputDir, requestUrl);
    if (file === undefined || !existsSync(file) || (await stat(file)).isDirectory()) { response.writeHead(404).end('Not found'); return; }
    if (extname(file) === '.html') {
      const html = await readFile(file, 'utf8');
      const body = /<\/body\s*>/i.test(html) ? html.replace(/<\/body\s*>/i, `${reloadClient}</body>`) : `${html}${reloadClient}`;
      response.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' }).end(body);
      return;
    }
    response.writeHead(200, { 'Content-Type': extname(file) === '.css' ? 'text/css; charset=utf-8' : 'application/octet-stream' });
    createReadStream(file).pipe(response);
  }
}

export async function startDevelopmentServer(options: ServeOptions = {}): Promise<DevelopmentServer> {
  return new DevServerPlugin().start(options);
}
