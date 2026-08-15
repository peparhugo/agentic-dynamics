import { createReadStream, existsSync, readFileSync, statSync } from 'node:fs';
import { createServer, IncomingMessage, ServerResponse } from 'node:http';
import { extname, join, normalize, resolve } from 'node:path';
import { BuildOptions, createBuildPipeline } from './generator';

const liveReloadScript = `<script>(() => { const socket = new WebSocket((location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/__ssg_live_reload'); socket.addEventListener('message', () => location.reload()); })();</script>`;
const mimeTypes: Record<string, string> = { '.css': 'text/css; charset=utf-8', '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.json': 'application/json; charset=utf-8', '.svg': 'image/svg+xml' };

export interface ServeOptions extends BuildOptions { port?: number; }
export interface DevelopmentServer { close(): Promise<void>; port: number; }

export function injectLiveReload(html: string): string {
  return /<\/body\s*>/i.test(html) ? html.replace(/<\/body\s*>/i, `${liveReloadScript}</body>`) : `${html}${liveReloadScript}`;
}

export function serveFile(request: IncomingMessage, response: ServerResponse, outputDir: string): void {
  const urlPath = decodeURIComponent(new URL(request.url ?? '/', 'http://localhost').pathname);
  const root = resolve(outputDir);
  let filePath = resolve(root, normalize(urlPath === '/' ? 'index.html' : urlPath.replace(/^\/+/, '')));
  if (!filePath.startsWith(`${root}/`) && filePath !== root) return void response.writeHead(403).end('Forbidden');
  if (existsSync(filePath) && statSync(filePath).isDirectory()) filePath = join(filePath, 'index.html');
  if (!existsSync(filePath) || !statSync(filePath).isFile()) return void response.writeHead(404).end('Not found');
  const type = mimeTypes[extname(filePath).toLowerCase()] ?? 'application/octet-stream';
  response.writeHead(200, { 'content-type': type });
  if (extname(filePath).toLowerCase() === '.html') response.end(injectLiveReload(readFileSync(filePath, 'utf8')));
  else createReadStream(filePath).pipe(response);
}

export function startServer({ port = 3000, ...options }: ServeOptions = {}): DevelopmentServer {
  const pipeline = createBuildPipeline({ ...options, port } as BuildOptions, 'serve');
  pipeline.build();
  return { port, close: () => pipeline.end() };
}
