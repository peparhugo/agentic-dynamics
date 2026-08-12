import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { URL } from 'node:url';
import chokidar, { FSWatcher } from 'chokidar';
import { WebSocketServer } from 'ws';
import type { BuildOptions } from '../src/generator';
import type { Plugin } from '../src/plugin';

export interface ServeOptions extends BuildOptions { port?: number; host?: string; }
export interface DevServer { server: http.Server; watcher: FSWatcher; close(): Promise<void>; }

const reloadScript = `<script>(function(){var socket=new WebSocket((location.protocol==='https:'?'wss://':'ws://')+location.host+'/__ssg_reload');socket.onmessage=function(event){if(event.data==='reload')location.reload()};socket.onclose=function(){setTimeout(function(){location.reload()},1000)}})();</script>`;
const injectReloadScript = (content: string): string => /<\/body\s*>/i.test(content) ? content.replace(/<\/body\s*>/i, `${reloadScript}</body>`) : `${content}${reloadScript}`;
const contentType = (filename: string): string => filename.endsWith('.html') ? 'text/html; charset=utf-8' : filename.endsWith('.css') ? 'text/css; charset=utf-8' : filename.endsWith('.js') ? 'text/javascript; charset=utf-8' : filename.endsWith('.json') ? 'application/json; charset=utf-8' : 'application/octet-stream';

export class DevServerPlugin implements Plugin {
  async start(options: ServeOptions, build: () => void): Promise<DevServer> {
    const outputDir = path.resolve(options.outputDir ?? './dist');
    const contentDir = path.resolve(options.contentDir ?? './content');
    const templatesDir = path.resolve(options.templatesDir ?? options.templateDir ?? './templates');
    const host = options.host ?? 'localhost';
    const sockets = new WebSocketServer({ noServer: true });
    build();
    const server = http.createServer((request, response) => {
      try {
        const requestPath = decodeURIComponent(new URL(request.url ?? '/', `http://${host}`).pathname);
        const relative = requestPath === '/' ? 'index.html' : requestPath.replace(/^\/+/, '');
        const filename = path.resolve(outputDir, relative);
        if (filename !== outputDir && !filename.startsWith(`${outputDir}${path.sep}`)) return void response.writeHead(403).end('Forbidden');
        if (!fs.existsSync(filename) || !fs.statSync(filename).isFile()) return void response.writeHead(404).end('Not found');
        let body = fs.readFileSync(filename);
        if (filename.endsWith('.html')) body = Buffer.from(injectReloadScript(body.toString('utf8')));
        response.writeHead(200, { 'Content-Type': contentType(filename) }).end(body);
      } catch { response.writeHead(400).end('Bad request'); }
    });
    server.on('upgrade', (request, socket, head) => {
      if (request.url !== '/__ssg_reload') return socket.destroy();
      sockets.handleUpgrade(request, socket, head, (client) => sockets.emit('connection', client, request));
    });
    sockets.on('connection', (client) => client.on('error', () => client.close()));
    let rebuildTimer: NodeJS.Timeout | undefined;
    const watcher = chokidar.watch([contentDir, templatesDir], { ignoreInitial: true });
    watcher.on('all', () => {
      if (rebuildTimer) clearTimeout(rebuildTimer);
      rebuildTimer = setTimeout(() => { try { build(); for (const client of sockets.clients) if (client.readyState === 1) client.send('reload'); } catch (error) { console.error(error instanceof Error ? error.message : error); } }, 50);
    });
    return new Promise((resolve, reject) => {
      server.once('error', reject);
      server.listen(options.port ?? 3000, host, () => {
        server.removeListener('error', reject);
        resolve({ server, watcher, close: async () => { if (rebuildTimer) clearTimeout(rebuildTimer); await watcher.close(); for (const client of sockets.clients) client.terminate(); sockets.close(); await new Promise<void>((done) => server.close(() => done())); } });
      });
    });
  }
}

export default DevServerPlugin;
