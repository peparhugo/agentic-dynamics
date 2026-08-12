import { createReadStream, promises as fs } from 'node:fs';
import http, { Server } from 'node:http';
import path from 'node:path';
import { WebSocketServer, WebSocket } from 'ws';
import chokidar, { FSWatcher } from 'chokidar';
import { buildSite } from '../index';
import type { BuildOptions } from '../index';
import { Plugin } from '../plugin';

export interface DevServerOptions extends BuildOptions { port?: number; host?: string; }
export interface DevServer { server: Server; watcher: FSWatcher; webSocketServer: WebSocketServer; close: () => Promise<void>; }
const contentTypes: Record<string, string> = { '.css': 'text/css; charset=utf-8', '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.json': 'application/json; charset=utf-8', '.svg': 'image/svg+xml', '.txt': 'text/plain; charset=utf-8' };
function injectLiveReload(html: string): string { const script = `<script>(function(){var socket=new WebSocket((location.protocol==='https:'?'wss://':'ws://')+location.host+'/__ssg_reload');socket.onmessage=function(event){if(event.data==='reload')location.reload();};socket.onclose=function(){setTimeout(function(){location.reload();},1000);};})();</script>`; return /<\/body\s*>/i.test(html) ? html.replace(/<\/body\s*>/i, `${script}</body>`) : `${html}${script}`; }
async function serveFile(response: http.ServerResponse, root: string, requestPath: string): Promise<void> { let relative = decodeURIComponent(requestPath.split('?')[0]); if (relative === '/') relative = '/index.html'; const file = path.resolve(root, `.${relative}`); if (file !== root && !file.startsWith(`${root}${path.sep}`)) { response.writeHead(403); response.end('Forbidden'); return; } try { const stat = await fs.stat(file); if (!stat.isFile()) throw new Error('not a file'); const extension = path.extname(file).toLowerCase(); if (extension === '.html') { response.writeHead(200, { 'Content-Type': contentTypes['.html'] }); response.end(injectLiveReload(await fs.readFile(file, 'utf8'))); return; } response.writeHead(200, { 'Content-Type': contentTypes[extension] ?? 'application/octet-stream' }); createReadStream(file).pipe(response); } catch { response.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' }); response.end('Not found'); } }

export class DevServerPlugin implements Plugin {}

export async function startDevServer(options: DevServerOptions = {}): Promise<DevServer> {
  const port = options.port ?? 3000, host = options.host ?? 'localhost'; const outputDir = path.resolve(options.outputDir ?? './dist'); const contentDir = path.resolve(options.contentDir ?? './content'); const templatesDir = path.resolve(options.templatesDir ?? './templates'); const buildOptions: BuildOptions = { ...options, contentDir, templatesDir, outputDir };
  await buildSite(buildOptions); const server = http.createServer((request, response) => { void serveFile(response, outputDir, request.url ?? '/'); }); const webSocketServer = new WebSocketServer({ noServer: true });
  server.on('upgrade', (request, socket, head) => { const requestUrl = new URL(request.url ?? '/', `http://${request.headers.host ?? host}`); if (requestUrl.pathname !== '/__ssg_reload') { socket.destroy(); return; } webSocketServer.handleUpgrade(request, socket, head, (client) => webSocketServer.emit('connection', client, request)); });
  let rebuildTimer: ReturnType<typeof setTimeout> | undefined, rebuilding = false, pending = false;
  const rebuild = async (): Promise<void> => { if (rebuilding) { pending = true; return; } rebuilding = true; try { await buildSite(buildOptions); webSocketServer.clients.forEach((client) => { if (client.readyState === WebSocket.OPEN) client.send('reload'); }); } catch (error) { process.stderr.write(`Build failed: ${error instanceof Error ? error.message : String(error)}\n`); } finally { rebuilding = false; if (pending) { pending = false; await rebuild(); } } };
  const watcher = chokidar.watch([contentDir, templatesDir], { ignoreInitial: true }); watcher.on('all', () => { if (rebuildTimer) clearTimeout(rebuildTimer); rebuildTimer = setTimeout(() => void rebuild(), 50); });
  await new Promise<void>((resolve, reject) => { server.once('error', reject); server.listen(port, host, () => { server.removeListener('error', reject); resolve(); }); });
  return { server, watcher, webSocketServer, close: async () => { if (rebuildTimer) clearTimeout(rebuildTimer); await watcher.close(); webSocketServer.close(); await new Promise<void>((resolve, reject) => server.close((error) => error ? reject(error) : resolve())); } };
}
