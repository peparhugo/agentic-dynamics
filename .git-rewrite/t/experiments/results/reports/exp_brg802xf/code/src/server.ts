import http from 'node:http';
import path from 'node:path';
import fs from 'node:fs/promises';
import { existsSync } from 'node:fs';
import mime from 'mime';
import chokidar from 'chokidar';
import { WebSocketServer } from 'ws';
import { GenerateOptions } from './types';
import { generateSite } from './generator';

export type ServerOptions = GenerateOptions & { port: number };

export async function startDevServer(opts: ServerOptions) {
  // Initial build with dev inject
  await generateSite({ ...opts, devInjectReload: true });

  const server = http.createServer(async (req, res) => {
    if (!req.url) { res.statusCode = 400; res.end('Bad Request'); return; }
    if (req.url === '/__livereload') { res.statusCode = 426; res.end('Use WebSocket'); return; }
    let reqPath = decodeURIComponent(req.url.split('?')[0]);
    if (reqPath.endsWith('/')) reqPath += 'index.html';
    const filePath = path.join(opts.outDir, reqPath);
    try {
      if (!existsSync(filePath)) {
        res.statusCode = 404; res.end('Not Found'); return;
      }
      const data = await fs.readFile(filePath);
      res.setHeader('Content-Type', mime.getType(filePath) || 'application/octet-stream');
      res.end(data);
    } catch (e: any) {
      res.statusCode = 500; res.end('Server Error');
    }
  });

  const wss = new WebSocketServer({ noServer: true });
  server.on('upgrade', (req, socket, head) => {
    const { url } = req;
    if (url && url.startsWith('/__livereload')) {
      wss.handleUpgrade(req, socket, head, ws => {
        wss.emit('connection', ws, req);
      });
    } else {
      socket.destroy();
    }
  });

  function broadcastReload() {
    for (const client of wss.clients) {
      if (client.readyState === 1) client.send('reload');
    }
  }

  const watcher = chokidar.watch([opts.srcDir, opts.templatesDir], { ignoreInitial: true });
  watcher.on('all', async () => {
    try {
      await generateSite({ ...opts, devInjectReload: true });
      broadcastReload();
    } catch (e) {
      // keep server alive
      // eslint-disable-next-line no-console
      console.error('Rebuild failed:', e);
    }
  });

  await new Promise<void>((resolve) => server.listen(opts.port, resolve));
  // eslint-disable-next-line no-console
  console.log(`Dev server running at http://localhost:${opts.port}`);

  return { server, close: async () => { await watcher.close(); wss.close(); server.close(); } };
}
