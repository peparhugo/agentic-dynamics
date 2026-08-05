import http from 'http';
import path from 'path';
import fs from 'fs';
import { lookup as lookupMime } from 'mime-types';
import chokidar from 'chokidar';
import WebSocket, { WebSocketServer } from 'ws';
import { buildSite } from './build';
import { BuildOptions } from './types';

function serveFile(filePath: string, res: http.ServerResponse) {
  fs.stat(filePath, (err, stat) => {
    if (err || !stat.isFile()) {
      res.statusCode = 404;
      res.end('Not found');
      return;
    }
    const type = lookupMime(path.extname(filePath)) || 'application/octet-stream';
    res.setHeader('Content-Type', type as string);
    fs.createReadStream(filePath).pipe(res);
  });
}

export async function serveWithLiveReload(opts: BuildOptions & { port: number }) {
  const port = opts.port;
  // Live reload client script injected into pages
  const clientScript = `\n<script>(function(){\n  var ws = new WebSocket('ws://'+location.hostname+':${port}');\n  ws.onmessage = function(msg){ if(msg.data==='reload'){ location.reload(); } };\n})();</script>\n`;

  await buildSite({ ...opts, liveReloadClient: clientScript });

  const outDir = path.resolve(opts.outDir);
  const server = http.createServer((req, res) => {
    const url = req.url || '/';
    const safePath = url.split('?')[0].split('#')[0];
    let filePath = path.join(outDir, safePath);
    if (filePath.endsWith('/')) filePath = path.join(filePath, 'index.html');
    if (!path.extname(filePath)) filePath += '.html';
    serveFile(filePath, res);
  });

  const wss = new WebSocketServer({ server });
  const broadcastReload = () => {
    for (const client of wss.clients) {
      if (client.readyState === WebSocket.OPEN) client.send('reload');
    }
  };

  const watcher = chokidar.watch([opts.srcDir, opts.templatesDir], { ignoreInitial: true });
  watcher.on('all', async () => {
    try {
      await buildSite({ ...opts, liveReloadClient: clientScript });
      broadcastReload();
    } catch (e) {
      // eslint-disable-next-line no-console
      console.error('Build error:', e);
    }
  });

  await new Promise<void>((resolve) => server.listen(port, resolve));
  // eslint-disable-next-line no-console
  console.log(`Serving ${outDir} at http://localhost:${port}`);

  return { close: async () => { await watcher.close(); server.close(); wss.close(); } };
}
