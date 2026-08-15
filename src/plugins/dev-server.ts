import { createServer, IncomingMessage, Server, ServerResponse } from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import { extname, relative, resolve } from 'node:path';
import chokidar from 'chokidar';
import { WebSocketServer } from 'ws';
import type { Plugin } from '../plugin';
import { buildSite, type BuildOptions } from '../site';

export interface DevServer { port: number; close(): Promise<void>; }
export interface DevServerOptions extends BuildOptions { port?: number; }

const liveReloadScript = '<script>(() => { const socket = new WebSocket(`${location.protocol === \'https:\' ? \'wss\' : \'ws\'}://${location.host}`); socket.addEventListener(\'message\', () => location.reload()); })();</script>';
const contentTypes: Record<string, string> = { '.css': 'text/css; charset=utf-8', '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.json': 'application/json; charset=utf-8', '.svg': 'image/svg+xml' };

function injectLiveReload(html: string): string {
  const bodyEnd = html.search(/<\/body\s*>/i);
  return bodyEnd === -1 ? `${html}${liveReloadScript}` : `${html.slice(0, bodyEnd)}${liveReloadScript}${html.slice(bodyEnd)}`;
}

async function serveFile(request: IncomingMessage, response: ServerResponse, outputDir: string): Promise<void> {
  let pathname: string;
  try { pathname = decodeURIComponent(new URL(request.url ?? '/', 'http://localhost').pathname); } catch { response.writeHead(400).end('Bad request'); return; }
  const file = resolve(outputDir, pathname === '/' ? 'index.html' : pathname.replace(/^\/+/, ''));
  if (relative(outputDir, file).startsWith('..')) { response.writeHead(403).end('Forbidden'); return; }
  try {
    if (!(await stat(file)).isFile()) throw new Error('Not a file');
    const extension = extname(file).toLowerCase();
    const body = extension === '.html' ? Buffer.from(injectLiveReload(await readFile(file, 'utf8'))) : await readFile(file);
    response.writeHead(200, { 'Content-Type': contentTypes[extension] ?? 'application/octet-stream' }).end(body);
  } catch { response.writeHead(404).end('Not found'); }
}

function listen(server: Server, port: number): Promise<void> {
  return new Promise((resolveListen, reject) => {
    server.once('error', reject);
    server.listen(port, '127.0.0.1', () => { server.off('error', reject); resolveListen(); });
  });
}

export class DevServerPlugin implements Plugin {
  constructor(private readonly options: DevServerOptions, private readonly setServer: (server: DevServer) => void) {}

  async onStart(context: Parameters<NonNullable<Plugin['onStart']>>[0]): Promise<void> {
      const { options, setServer } = this;
      await buildSite({ ...options, contentDir: context.contentDir, templateDir: context.templateDir, outputDir: context.outputDir });
      const server = createServer((request, response) => { void serveFile(request, response, context.outputDir); });
      const sockets = new WebSocketServer({ server });
      await listen(server, options.port ?? 3000);
      let building = false;
      let rebuildQueued = false;
      const rebuild = async (): Promise<void> => {
        if (building) { rebuildQueued = true; return; }
        building = true;
        try {
          await buildSite({ ...options, contentDir: context.contentDir, templateDir: context.templateDir, outputDir: context.outputDir });
          for (const client of sockets.clients) client.send('reload');
          process.stdout.write('Rebuilt site.\n');
        } catch (error: unknown) { process.stderr.write(`Build failed: ${error instanceof Error ? error.message : String(error)}\n`); }
        finally { building = false; if (rebuildQueued) { rebuildQueued = false; void rebuild(); } }
      };
      const watcher = chokidar.watch([context.contentDir, context.templateDir], { ignoreInitial: true });
      watcher.on('all', () => { void rebuild(); });
      await new Promise<void>((resolveReady) => watcher.once('ready', resolveReady));
      const address = server.address();
      if (!address || typeof address === 'string') throw new Error('Could not determine server port');
      setServer({
        port: address.port,
        async close(): Promise<void> {
          await watcher.close();
          for (const client of sockets.clients) client.terminate();
          await new Promise<void>((resolveClose) => sockets.close(() => resolveClose()));
          await new Promise<void>((resolveClose, reject) => server.close((error) => error ? reject(error) : resolveClose()));
        },
      });
  }
}
