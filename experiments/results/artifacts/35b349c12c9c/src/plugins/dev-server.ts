import http from 'http';
import fs from 'fs/promises';
import path from 'path';
import chokidar, { FSWatcher } from 'chokidar';
import { WebSocketServer, WebSocket } from 'ws';
import { buildSite } from '../site-generator';
import type { BuildOptions } from '../site-generator';
import { Plugin } from '../plugin';

export interface DevServerOptions extends BuildOptions { port?: number; host?: string; }
export interface DevServer { server: http.Server; watcher: FSWatcher; close(): Promise<void>; }
const reloadScript = `<script>(function(){var protocol=location.protocol==='https:'?'wss':'ws';var socket=new WebSocket(protocol+'://'+location.host+'/__ssg_reload');socket.onmessage=function(event){if(event.data==='reload')location.reload();};socket.onclose=function(){setTimeout(function(){location.reload();},1000);};})();</script>`;
function injectReloadScript(source: string): string { const closingBody = source.lastIndexOf('</body>'); return closingBody === -1 ? `${source}${reloadScript}` : `${source.slice(0, closingBody)}${reloadScript}${source.slice(closingBody)}`; }
function contentType(filePath: string): string { if (filePath.endsWith('.html')) return 'text/html; charset=utf-8'; if (filePath.endsWith('.css')) return 'text/css; charset=utf-8'; if (filePath.endsWith('.js')) return 'text/javascript; charset=utf-8'; if (filePath.endsWith('.json')) return 'application/json; charset=utf-8'; return 'application/octet-stream'; }

export class DevServerPlugin implements Plugin {
  async start(options: DevServerOptions = {}): Promise<DevServer> {
    const buildOptions: BuildOptions = { contentDir: options.contentDir, outputDir: options.outputDir, templatesDir: options.templatesDir, defaultTemplate: options.defaultTemplate, configFile: options.configFile, plugins: options.plugins };
    const outputDir = path.resolve(buildOptions.outputDir ?? './dist');
    const contentDir = path.resolve(buildOptions.contentDir ?? './content');
    const templatesDir = path.resolve(buildOptions.templatesDir ?? './templates');
    const port = options.port ?? 3000;
    const host = options.host ?? 'localhost';
    await buildSite(buildOptions);
    const server = http.createServer(async (request, response) => {
      const requestPath = decodeURIComponent((request.url ?? '/').split('?')[0]);
      const relativePath = requestPath === '/' ? 'index.html' : requestPath.replace(/^\/+/, '');
      const filePath = path.resolve(outputDir, relativePath);
      if (filePath !== outputDir && !filePath.startsWith(`${outputDir}${path.sep}`)) { response.writeHead(403); response.end('Forbidden'); return; }
      try { const file = await fs.readFile(filePath); const body = filePath.endsWith('.html') ? injectReloadScript(file.toString('utf8')) : file; response.writeHead(200, { 'Content-Type': contentType(filePath) }); response.end(body); } catch { response.writeHead(404); response.end('Not found'); }
    });
    const webSocket = new WebSocketServer({ server, path: '/__ssg_reload' });
    const watcher = chokidar.watch([contentDir, templatesDir], { ignoreInitial: true });
    let rebuilding = false; let pending = false;
    const rebuild = async (): Promise<void> => {
      if (rebuilding) { pending = true; return; }
      rebuilding = true;
      try { await buildSite(buildOptions); webSocket.clients.forEach((client) => { if (client.readyState === WebSocket.OPEN) client.send('reload'); }); }
      catch (error) { console.error(error instanceof Error ? error.message : error); }
      finally { rebuilding = false; if (pending) { pending = false; void rebuild(); } }
    };
    watcher.on('add', () => void rebuild()).on('change', () => void rebuild()).on('unlink', () => void rebuild());
    await new Promise<void>((resolve, reject) => { server.once('error', reject); server.listen(port, host, () => resolve()); });
    console.log(`Serving ${outputDir} at http://${host}:${port}`);
    return { server, watcher, async close(): Promise<void> { await watcher.close(); await new Promise<void>((resolve, reject) => webSocket.close((error) => error ? reject(error) : resolve())); await new Promise<void>((resolve, reject) => server.close((error) => error ? reject(error) : resolve())); } };
  }
}

export async function startDevServer(options: DevServerOptions = {}): Promise<DevServer> { return new DevServerPlugin().start(options); }
