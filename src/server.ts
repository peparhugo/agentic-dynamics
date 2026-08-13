import { createReadStream } from 'node:fs';
import { access, readFile } from 'node:fs/promises';
import { createServer, type Server } from 'node:http';
import path from 'node:path';
import chokidar, { type FSWatcher } from 'chokidar';
import { WebSocketServer } from 'ws';
import { buildSite, type BuildOptions } from './generator.js';

export interface ServeOptions extends BuildOptions {
  port?: number;
}

export interface DevelopmentServer {
  port: number;
  close(): Promise<void>;
}

const reloadScript = '<script>(() => {\n'
  + '  const connect = () => {\n'
  + "    const socket = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}`);\n"
  + "    socket.addEventListener('message', () => location.reload());\n"
  + "    socket.addEventListener('close', () => setTimeout(connect, 1000));\n"
  + '  };\n'
  + '  connect();\n'
  + '})();</script>';

function htmlWithReloadScript(html: string): string {
  return /<\/body\s*>/i.test(html)
    ? html.replace(/<\/body\s*>/i, `${reloadScript}</body>`)
    : `${html}${reloadScript}`;
}

function contentType(file: string): string {
  if (file.endsWith('.html')) return 'text/html; charset=utf-8';
  if (file.endsWith('.css')) return 'text/css; charset=utf-8';
  if (file.endsWith('.js')) return 'text/javascript; charset=utf-8';
  if (file.endsWith('.json')) return 'application/json; charset=utf-8';
  if (file.endsWith('.svg')) return 'image/svg+xml';
  return 'application/octet-stream';
}

async function fileExists(file: string): Promise<boolean> {
  try {
    await access(file);
    return true;
  } catch {
    return false;
  }
}

export async function serveSite(options: ServeOptions = {}): Promise<DevelopmentServer> {
  const port = options.port ?? 3000;
  const contentDir = path.resolve(options.contentDir ?? 'content');
  const templatesDir = path.resolve(options.templatesDir ?? 'templates');
  const outputDir = path.resolve(options.outputDir ?? 'dist');
  const buildOptions = { contentDir, templatesDir, outputDir };
  await buildSite(buildOptions);

  const server = createServer(async (request, response) => {
    const pathname = new URL(request.url ?? '/', 'http://localhost').pathname;
    const requestedFile = pathname === '/' ? 'index.html' : decodeURIComponent(pathname).replace(/^\/+/, '');
    const file = path.resolve(outputDir, requestedFile);
    if (!file.startsWith(`${outputDir}${path.sep}`) && file !== outputDir) {
      response.writeHead(403).end();
      return;
    }
    if (!await fileExists(file)) {
      response.writeHead(404).end('Not found');
      return;
    }
    response.setHeader('Content-Type', contentType(file));
    if (file.endsWith('.html')) response.end(htmlWithReloadScript(await readFile(file, 'utf8')));
    else createReadStream(file).pipe(response);
  });
  const sockets = new WebSocketServer({ server });
  const watcher = chokidar.watch([contentDir, templatesDir], { ignoreInitial: true });
  let rebuilding = false;
  let rebuildQueued = false;
  const rebuild = async (): Promise<void> => {
    if (rebuilding) {
      rebuildQueued = true;
      return;
    }
    rebuilding = true;
    try {
      await buildSite(buildOptions);
      for (const socket of sockets.clients) socket.send('reload');
      process.stdout.write('Rebuilt site.\n');
    } catch (error: unknown) {
      process.stderr.write(`Build failed: ${error instanceof Error ? error.message : String(error)}\n`);
    } finally {
      rebuilding = false;
      if (rebuildQueued) {
        rebuildQueued = false;
        await rebuild();
      }
    }
  };
  watcher.on('all', () => { void rebuild(); });
  await new Promise<void>((resolve) => watcher.once('ready', resolve));

  await new Promise<void>((resolve, reject) => {
    server.once('error', reject);
    server.listen(port, 'localhost', () => {
      server.off('error', reject);
      resolve();
    });
  });
  const address = server.address();
  if (!address || typeof address === 'string') throw new Error('Could not determine server port');
  process.stdout.write(`Serving ${outputDir} at http://localhost:${address.port}\n`);
  return {
    port: address.port,
    close: async () => {
      await watcher.close();
      for (const socket of sockets.clients) socket.terminate();
      await new Promise<void>((resolve, reject) => sockets.close((error) => error ? reject(error) : resolve()));
      await new Promise<void>((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
    }
  };
}
