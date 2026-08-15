import { promises as fs } from 'node:fs';
import path from 'node:path';
import { createServer, type IncomingMessage, type ServerResponse } from 'node:http';
import chokidar, { type FSWatcher } from 'chokidar';
import { WebSocketServer, type WebSocket } from 'ws';
import type { DevServer, ServeOptions } from '../index';
import type { Plugin } from './types';

const liveReloadScript = `<script>(function(){var socket=new WebSocket('ws://'+location.host+'/_ssg_live_reload');socket.onmessage=function(event){if(event.data==='reload')location.reload()};socket.onclose=function(){setTimeout(function(){location.reload()},1000)}})();</script>`;
export function injectLiveReload(html: string): string { if (html.includes("new WebSocket('ws://' + location.host")) return html; const closingBody = html.search(/<\/body\s*>/i); return closingBody < 0 ? `${html}${liveReloadScript}` : `${html.slice(0, closingBody)}${liveReloadScript}${html.slice(closingBody)}`; }
function contentType(filePath: string): string { return ({ '.css': 'text/css; charset=utf-8', '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.json': 'application/json; charset=utf-8', '.svg': 'image/svg+xml' } as Record<string, string>)[path.extname(filePath).toLowerCase()] ?? 'application/octet-stream'; }
async function serveFile(outputDir: string, request: IncomingMessage, response: ServerResponse): Promise<void> {
  const requested = decodeURIComponent((request.url ?? '/').split('?')[0]); const relative = requested === '/' ? 'index.html' : requested.replace(/^\/+/, ''); const outputRoot = path.resolve(outputDir); const filePath = path.resolve(outputRoot, relative);
  if (filePath !== outputRoot && !filePath.startsWith(`${outputRoot}${path.sep}`)) { response.writeHead(403); response.end('Forbidden'); return; }
  try { const file = await fs.readFile(filePath); response.writeHead(200, { 'Content-Type': contentType(filePath) }); response.end(path.extname(filePath).toLowerCase() === '.html' ? injectLiveReload(file.toString()) : file); } catch { response.writeHead(404); response.end('Not found'); }
}

export class DevServerPlugin implements Plugin {
  async start(options: ServeOptions, build: (options: ServeOptions) => Promise<unknown>): Promise<DevServer> {
    const outputDir = path.resolve(options.outputDir ?? './dist'); const contentDir = path.resolve(options.contentDir ?? './content'); const templatesDir = path.resolve(options.templatesDir ?? './templates');
    await build({ ...options, contentDir, outputDir, templatesDir });
    const clients = new Set<WebSocket>(); const webSocketServer = new WebSocketServer({ noServer: true });
    webSocketServer.on('connection', (socket) => { clients.add(socket); socket.on('close', () => clients.delete(socket)); }); webSocketServer.on('close', () => clients.clear());
    const server = createServer((request, response) => { void serveFile(outputDir, request, response); });
    server.on('upgrade', (request, socket, head) => { if (request.url !== '/_ssg_live_reload') { socket.destroy(); return; } webSocketServer.handleUpgrade(request, socket, head, (client) => webSocketServer.emit('connection', client, request)); });
    const watcher = chokidar.watch([contentDir, templatesDir], { ignoreInitial: true }); let rebuilding = false; let queued = false;
    const rebuild = async (): Promise<void> => { if (rebuilding) { queued = true; return; } rebuilding = true; try { await build({ contentDir, outputDir, templatesDir }); for (const client of clients) if (client.readyState === client.OPEN) client.send('reload'); } catch (error: unknown) { console.error(error instanceof Error ? error.message : error); } finally { rebuilding = false; if (queued) { queued = false; void rebuild(); } } };
    watcher.on('all', () => void rebuild()); await new Promise<void>((resolve) => server.listen(options.port ?? 3000, 'localhost', resolve));
    return { server, watcher, close: async () => { await watcher.close(); for (const client of clients) client.terminate(); await new Promise<void>((resolve, reject) => server.close((error) => error ? reject(error) : resolve())); await new Promise<void>((resolve) => webSocketServer.close(() => resolve())); } };
  }
}
