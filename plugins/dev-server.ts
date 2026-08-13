import { promises as fs } from 'node:fs';
import { createServer, type Server } from 'node:http';
import path from 'node:path';
import chokidar, { type FSWatcher } from 'chokidar';
import { WebSocketServer } from 'ws';
import { buildSite, type BuildOptions } from '../src/generator.js';
import type { DevelopmentServer, Plugin } from './types.js';

export interface ServeOptions extends BuildOptions { port?: number; }

const reloadScript = '<script>new WebSocket(`ws://${location.host}`).addEventListener("message", () => location.reload());</script>';

function withReloadScript(html: string): string {
  return html.includes('</body>') ? html.replace('</body>', `${reloadScript}</body>`) : `${html}${reloadScript}`;
}

async function serveFile(requestPath: string, outputDir: string, response: import('node:http').ServerResponse): Promise<void> {
  const relativePath = requestPath === '/' ? 'index.html' : decodeURIComponent(requestPath).replace(/^\/+/, '');
  const file = path.resolve(outputDir, relativePath);
  if (!file.startsWith(`${outputDir}${path.sep}`) && file !== path.join(outputDir, 'index.html')) return void response.writeHead(403).end();
  try {
    const stat = await fs.stat(file);
    if (!stat.isFile()) throw new Error('Not a file');
    if (path.extname(file) === '.html') return void response.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' }).end(withReloadScript(await fs.readFile(file, 'utf8')));
    response.writeHead(200).end(await fs.readFile(file));
  } catch { response.writeHead(404).end('Not found'); }
}

export class DevServerPlugin implements Plugin {
  constructor(private readonly options: ServeOptions = {}) {}

  async start(): Promise<DevelopmentServer> {
    const outputDir = path.resolve('./dist');
    const contentDir = path.resolve(this.options.contentDir ?? './content');
    const templatesDir = path.resolve(this.options.templatesDir ?? './templates');
    const server = createServer((request, response) => void serveFile(new URL(request.url ?? '/', 'http://localhost').pathname, outputDir, response));
    const sockets = new WebSocketServer({ server });
    const rebuild = async (): Promise<void> => {
      try {
        const pages = await buildSite({ contentDir, templatesDir, outputDir, plugins: this.options.plugins });
        process.stdout.write(`Generated ${pages.length} page(s).\n`);
        sockets.clients.forEach((client) => client.send('reload'));
      } catch (error) { process.stderr.write(`Build failed: ${error instanceof Error ? error.message : String(error)}\n`); }
    };
    await rebuild();
    const watcher = chokidar.watch([contentDir, templatesDir], { ignoreInitial: true });
    watcher.on('all', () => void rebuild());
    await new Promise<void>((resolve) => server.listen(this.options.port ?? 3000, 'localhost', resolve));
    return { server, watcher, close: async () => {
      await watcher.close();
      sockets.clients.forEach((client) => client.close());
      sockets.close();
      await new Promise<void>((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
    } };
  }
}

export async function startDevelopmentServer(options: ServeOptions = {}): Promise<DevelopmentServer> {
  return new DevServerPlugin(options).start();
}
