#!/usr/bin/env node
import { promises as fs } from 'node:fs';
import { createServer, type Server } from 'node:http';
import path from 'node:path';
import chokidar, { type FSWatcher } from 'chokidar';
import { WebSocketServer } from 'ws';
import { buildSite } from './generator.js';

function usage(): string {
  return 'Usage: ssg build [--content <dir>] [--output <dir>] [--templates <dir>]\n       ssg serve [--content <dir>] [--templates <dir>] [--port <port>]';
}

export interface CliOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
  port?: number;
}

export function parseArguments(args: string[]): CliOptions {
  const command = args[0];
  if (command !== 'build' && command !== 'serve') throw new Error(usage());
  const options: CliOptions = {};
  for (let index = 1; index < args.length; index += 1) {
    const flag = args[index];
    const value = args[index + 1];
    if ((flag !== '--content' && flag !== '--output' && flag !== '--templates' && flag !== '--port') || !value || value.startsWith('--')) throw new Error(usage());
    if ((command === 'serve' && flag === '--output') || (command === 'build' && flag === '--port')) throw new Error(usage());
    if (flag === '--content') options.contentDir = value;
    if (flag === '--output') options.outputDir = value;
    if (flag === '--templates') options.templatesDir = value;
    if (flag === '--port') {
      const port = Number(value);
      if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error(usage());
      options.port = port;
    }
    index += 1;
  }
  return options;
}

const reloadScript = '<script>new WebSocket(`ws://${location.host}`).addEventListener("message", () => location.reload());</script>';

function withReloadScript(html: string): string {
  return html.includes('</body>') ? html.replace('</body>', `${reloadScript}</body>`) : `${html}${reloadScript}`;
}

async function serveFile(requestPath: string, outputDir: string, response: import('node:http').ServerResponse): Promise<void> {
  const relativePath = requestPath === '/' ? 'index.html' : decodeURIComponent(requestPath).replace(/^\/+/, '');
  const file = path.resolve(outputDir, relativePath);
  if (!file.startsWith(`${outputDir}${path.sep}`) && file !== path.join(outputDir, 'index.html')) {
    response.writeHead(403).end();
    return;
  }
  try {
    const stat = await fs.stat(file);
    if (!stat.isFile()) throw new Error('Not a file');
    if (path.extname(file) === '.html') {
      response.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' }).end(withReloadScript(await fs.readFile(file, 'utf8')));
      return;
    }
    response.writeHead(200).end(await fs.readFile(file));
  } catch {
    response.writeHead(404).end('Not found');
  }
}

export interface DevelopmentServer {
  server: Server;
  watcher: FSWatcher;
  close(): Promise<void>;
}

export async function startDevelopmentServer(options: CliOptions = {}): Promise<DevelopmentServer> {
  const outputDir = path.resolve('./dist');
  const contentDir = path.resolve(options.contentDir ?? './content');
  const templatesDir = path.resolve(options.templatesDir ?? './templates');
  const server = createServer((request, response) => void serveFile(new URL(request.url ?? '/', 'http://localhost').pathname, outputDir, response));
  const sockets = new WebSocketServer({ server });
  const rebuild = async (): Promise<void> => {
    try {
      const pages = await buildSite({ contentDir, templatesDir, outputDir });
      process.stdout.write(`Generated ${pages.length} page(s).\n`);
      sockets.clients.forEach((client) => client.send('reload'));
    } catch (error) {
      process.stderr.write(`Build failed: ${error instanceof Error ? error.message : String(error)}\n`);
    }
  };
  await rebuild();
  const watcher = chokidar.watch([contentDir, templatesDir], { ignoreInitial: true });
  watcher.on('all', () => void rebuild());
  await new Promise<void>((resolve) => server.listen(options.port ?? 3000, 'localhost', resolve));
  return {
    server,
    watcher,
    close: async () => {
      await watcher.close();
      sockets.clients.forEach((client) => client.close());
      sockets.close();
      await new Promise<void>((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
    },
  };
}

async function main(): Promise<void> {
  try {
    const args = process.argv.slice(2);
    const options = parseArguments(args);
    if (args[0] === 'serve') {
      const server = await startDevelopmentServer(options);
      const address = server.server.address();
      const port = typeof address === 'object' && address ? address.port : options.port ?? 3000;
      process.stdout.write(`Serving at http://localhost:${port}\n`);
      return;
    }
    const pages = await buildSite(options);
    process.stdout.write(`Generated ${pages.length} page(s).\n`);
  } catch (error) {
    process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
    process.exitCode = 1;
  }
}

void main();
