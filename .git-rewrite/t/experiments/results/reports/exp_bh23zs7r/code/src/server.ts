import express from 'express';
import { WebSocketServer } from 'ws';
import chokidar from 'chokidar';
import path from 'node:path';
import type { DevServerOptions } from './types.js';
import { buildSite } from './generator.js';

export async function startDevServer(opts: DevServerOptions) {
  const port = opts.port ?? 5173;
  const wsPort = port + 1; // simple separation
  const liveReloadUrl = `ws://localhost:${wsPort}`;

  // initial build with live reload injection
  await buildSite({ ...opts, liveReloadUrl });

  // Static server
  const app = express();
  app.use(express.static(opts.outDir));

  const server = app.listen(port, () => {
    // eslint-disable-next-line no-console
    console.log(`Dev server at http://localhost:${port}`);
  });

  // WebSocket for live reload
  const wss = new WebSocketServer({ port: wsPort });

  function broadcastReload() {
    for (const client of wss.clients) {
      try {
        client.send('reload');
      } catch {}
    }
  }

  // Watcher
  const watcher = chokidar.watch([opts.sourceDir, opts.templatesDir], {
    ignoreInitial: true,
  });
  watcher.on('all', async () => {
    try {
      await buildSite({ ...opts, liveReloadUrl });
      broadcastReload();
    } catch (e) {
      // eslint-disable-next-line no-console
      console.error('Build error', e);
    }
  });

  return {
    close: async () => {
      await watcher.close();
      wss.close();
      await new Promise<void>((res) => server.close(() => res()));
    },
    port,
    wsPort,
    outDir: path.resolve(opts.outDir),
  };
}
