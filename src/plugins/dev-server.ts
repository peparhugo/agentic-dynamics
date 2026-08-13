import { createReadStream } from 'node:fs';
import { access, readFile } from 'node:fs/promises';
import { createServer, IncomingMessage, ServerResponse } from 'node:http';
import { extname, join, resolve, sep } from 'node:path';
import chokidar from 'chokidar';
import { WebSocketServer } from 'ws';
import { buildSite } from '../generator';
import { BuildOptions, Plugin } from '../plugin';

export interface ServeOptions extends BuildOptions {
  port?: number;
}

export interface DevServer {
  port: number;
  close(): Promise<void>;
}

const liveReloadScript = '<script>(function(){var socket=new WebSocket((location.protocol==="https:"?"wss://":"ws://")+location.host+"/__ssg_live_reload");socket.addEventListener("message",function(){location.reload();});}());</script>';
const mimeTypes: Record<string, string> = { '.css': 'text/css; charset=utf-8', '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.json': 'application/json; charset=utf-8', '.svg': 'image/svg+xml' };

function requestPath(request: IncomingMessage): string {
  const pathname = new URL(request.url ?? '/', 'http://localhost').pathname;
  const decoded = decodeURIComponent(pathname);
  return decoded.endsWith('/') ? `${decoded}index.html` : decoded;
}

async function serveFile(root: string, request: IncomingMessage, response: ServerResponse): Promise<void> {
  const file = resolve(root, `.${requestPath(request)}`);
  if (file !== root && !file.startsWith(`${root}${sep}`)) return void response.writeHead(403).end('Forbidden');
  let destination = file;
  try { await access(destination); } catch {
    if (!extname(destination)) destination = join(destination, 'index.html');
    try { await access(destination); } catch { return void response.writeHead(404).end('Not Found'); }
  }
  response.setHeader('Content-Type', mimeTypes[extname(destination).toLowerCase()] ?? 'application/octet-stream');
  if (extname(destination).toLowerCase() === '.html') {
    const html = await readFile(destination, 'utf8');
    response.end(html.includes('</body>') ? html.replace('</body>', `${liveReloadScript}</body>`) : `${html}${liveReloadScript}`);
  } else createReadStream(destination).pipe(response);
}

export class DevServerPlugin implements Plugin {
  async start(options: ServeOptions = {}): Promise<DevServer> {
    const outputDir = resolve(options.outputDir ?? 'dist');
    const buildOptions: BuildOptions = { ...options, outputDir, incremental: true };
    await buildSite(buildOptions);
    const server = createServer((request, response) => void serveFile(outputDir, request, response).catch(() => response.writeHead(500).end('Internal Server Error')));
    const webSockets = new WebSocketServer({ server, path: '/__ssg_live_reload' });
    let rebuilding = false;
    let queued = false;
    const rebuild = async (): Promise<void> => {
      if (rebuilding) { queued = true; return; }
      rebuilding = true;
      try {
        await buildSite(buildOptions);
        webSockets.clients.forEach((client) => client.send('reload'));
        process.stdout.write('Rebuilt site.\n');
      } catch (error: unknown) {
        process.stderr.write(`Rebuild failed: ${error instanceof Error ? error.message : String(error)}\n`);
      } finally {
        rebuilding = false;
        if (queued) { queued = false; void rebuild(); }
      }
    };
    const watcher = chokidar.watch([resolve(options.contentDir ?? 'content'), resolve(options.templatesDir ?? 'templates')], { ignoreInitial: true });
    watcher.on('all', () => void rebuild());
    await new Promise<void>((resolveListen, reject) => {
      server.once('error', reject);
      server.listen(options.port ?? 3000, 'localhost', () => { server.off('error', reject); resolveListen(); });
    });
    const address = server.address();
    if (!address || typeof address === 'string') throw new Error('Unable to determine dev server port');
    return {
      port: address.port,
      async close(): Promise<void> {
        await watcher.close();
        webSockets.clients.forEach((client) => client.terminate());
        await new Promise<void>((resolveClose, reject) => webSockets.close((error) => error ? reject(error) : resolveClose()));
        await new Promise<void>((resolveClose, reject) => server.close((error) => error ? reject(error) : resolveClose()));
      },
    };
  }
}
