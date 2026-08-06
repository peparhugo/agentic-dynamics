import http from 'node:http';
import path from 'node:path';
import express from 'express';
import serveStatic from 'serve-static';
import chokidar from 'chokidar';
import { WebSocketServer } from 'ws';
import { BuildOptions } from './types';
import { buildSite } from './build';

export type ServerOptions = BuildOptions & { port: number };

export async function startDevServer(opts: ServerOptions) {
  const app = express();
  const server = http.createServer(app);
  const wss = new WebSocketServer({ server, path: '/_livereload' });

  function broadcastReload() {
    for (const client of wss.clients) {
      if (client.readyState === 1) client.send('reload');
    }
  }

  // Initial build
  await buildSite({ ...opts, liveReload: true });

  // Serve static
  app.use(serveStatic(opts.outDir, { extensions: ['html'], index: ['index.html'] }));

  // Watcher
  const watcher = chokidar.watch([opts.srcDir, opts.templatesDir], { ignoreInitial: true });
  let building = false;
  let pending = false;
  async function rebuild() {
    if (building) { pending = true; return; }
    building = true;
    try {
      await buildSite({ ...opts, liveReload: true });
      broadcastReload();
    } catch (e) {
      // eslint-disable-next-line no-console
      console.error('Build failed:', e);
    } finally {
      building = false;
      if (pending) { pending = false; rebuild(); }
    }
  }
  watcher.on('add', rebuild).on('change', rebuild).on('unlink', rebuild);

  await new Promise<void>((resolve) => {
    server.listen(opts.port, () => resolve());
  });

  const url = `http://localhost:${opts.port}`;
  return { server, url, stop: async () => { await watcher.close(); await new Promise(r => server.close(() => r(null))); } };
}
