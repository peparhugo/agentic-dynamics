import { createReadStream } from 'node:fs';
import { readFile, stat } from 'node:fs/promises';
import { createServer, IncomingMessage, ServerResponse } from 'node:http';
import { extname, resolve, sep } from 'node:path';
import chokidar from 'chokidar';
import { WebSocketServer } from 'ws';
import { BuildOptions, buildSite } from '../generator';
import { Plugin } from '../plugin';

export interface ServeOptions extends BuildOptions { port?: number; }
export interface DevelopmentServer { port: number; close(): Promise<void>; }
const liveReloadScript = '<script>(() => { const socket = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}`); socket.onmessage = () => location.reload(); })();</script>';

function contentType(path: string): string { switch (extname(path).toLowerCase()) { case '.html': return 'text/html; charset=utf-8'; case '.css': return 'text/css; charset=utf-8'; case '.js': return 'text/javascript; charset=utf-8'; case '.json': return 'application/json; charset=utf-8'; case '.svg': return 'image/svg+xml'; default: return 'application/octet-stream'; } }
function injectLiveReload(html: string): string { return /<\/body>/i.test(html) ? html.replace(/<\/body>/i, `${liveReloadScript}</body>`) : `${html}${liveReloadScript}`; }
async function serveFile(request: IncomingMessage, response: ServerResponse, outputDir: string): Promise<void> {
  const pathname = new URL(request.url ?? '/', 'http://localhost').pathname;
  const relativePath = pathname === '/' ? 'index.html' : decodeURIComponent(pathname).replace(/^[/\\]+/, '');
  const filePath = resolve(outputDir, relativePath);
  if (filePath !== outputDir && !filePath.startsWith(`${outputDir}${sep}`)) { response.writeHead(403).end(); return; }
  try {
    if (!(await stat(filePath)).isFile()) throw new Error('Not a file');
    if (extname(filePath).toLowerCase() === '.html') { response.writeHead(200, { 'Content-Type': contentType(filePath), 'Cache-Control': 'no-cache' }).end(injectLiveReload(await readFile(filePath, 'utf8'))); return; }
    response.writeHead(200, { 'Content-Type': contentType(filePath), 'Cache-Control': 'no-cache' }); createReadStream(filePath).pipe(response);
  } catch { response.writeHead(404).end('Not found'); }
}

export const DevServerPlugin: Plugin & { serve(options?: ServeOptions): Promise<DevelopmentServer> } = {
  onStart() {},
  async serve(options: ServeOptions = {}): Promise<DevelopmentServer> {
    const outputDir = resolve(options.outputDir ?? 'dist');
    const contentDir = resolve(options.contentDir ?? 'content');
    const templateDir = resolve(options.templateDir ?? 'templates');
    const port = options.port ?? 3000;
    const server = createServer((request, response) => { void serveFile(request, response, outputDir); });
    const sockets = new WebSocketServer({ server });
    let rebuilding = false;
    let queued = false;
    const rebuild = async (): Promise<void> => {
      if (rebuilding) { queued = true; return; }
      rebuilding = true;
      try { const pages = await buildSite({ ...options, contentDir, templateDir, outputDir }); console.log(`Generated ${pages.length} page(s).`); for (const client of sockets.clients) client.send('reload'); }
      catch (error) { console.error(error instanceof Error ? error.message : error); }
      finally { rebuilding = false; if (queued) { queued = false; await rebuild(); } }
    };
    await rebuild();
    const watcher = chokidar.watch([contentDir, templateDir], { ignoreInitial: true });
    watcher.on('all', () => { void rebuild(); });
    await new Promise<void>((accept) => watcher.once('ready', accept));
    await new Promise<void>((accept, reject) => { server.once('error', reject); server.listen(port, 'localhost', () => { server.off('error', reject); accept(); }); });
    const address = server.address();
    const activePort = typeof address === 'object' && address ? address.port : port;
    console.log(`Serving ${outputDir} at http://localhost:${activePort}`);
    return { port: activePort, async close(): Promise<void> { await watcher.close(); for (const client of sockets.clients) client.terminate(); await new Promise<void>((accept) => sockets.close(() => accept())); await new Promise<void>((accept, reject) => server.close((error) => error ? reject(error) : accept())); } };
  },
};
