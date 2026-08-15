import express, { Express, Request, Response } from 'express';
import path from 'path';
import { WebSocketServer, WebSocket } from 'ws';
import { createServer, Server as HttpServer } from 'http';
import chokidar, { FSWatcher } from 'chokidar';
import { promises as fs } from 'fs';
import { readMarkdownFiles } from './files';
import { processMarkdownFile } from './page';
import { generatePageHtml, generateIndexHtml } from './generator';

let clients: WebSocket[] = [];

function broadcastReload(): void {
  const message = JSON.stringify({ type: 'reload' });
  clients = clients.filter(client => client.readyState === WebSocket.OPEN);
  clients.forEach(client => {
    client.send(message);
  });
}

function injectReloadScript(html: string): string {
  const script = `<script>
(function() {
  const ws = new WebSocket('ws://' + window.location.host);
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === 'reload') {
      window.location.reload();
    }
  };
  ws.onerror = () => {
    setTimeout(() => {
      window.location.reload();
    }, 1000);
  };
})();
</script>`;

  if (html.includes('</body>')) {
    return html.replace('</body>', script + '\n</body>');
  }
  return html + script;
}

async function serveFile(filePath: string, distDir: string): Promise<string> {
  try {
    let content = await fs.readFile(filePath, 'utf-8');

    if (filePath.endsWith('.html')) {
      content = injectReloadScript(content);
    }

    return content;
  } catch (error) {
    throw error;
  }
}

async function rebuild(
  contentDir: string,
  distDir: string,
  templateDir: string | undefined
): Promise<void> {
  try {
    console.log('Rebuilding...');
    const files = await readMarkdownFiles(contentDir);

    if (files.length === 0) {
      console.log('No markdown files found.');
      return;
    }

    const pages = [];
    for (const file of files) {
      const page = await processMarkdownFile(file.name, file.content);
      pages.push(page);
      await generatePageHtml(page, distDir, templateDir);
    }

    await generateIndexHtml(pages, distDir);
    console.log('Build complete, reloading browser...');
    broadcastReload();
  } catch (error) {
    console.error('Rebuild error:', (error as Error).message);
  }
}

export async function serve(
  distDir: string,
  contentDir: string,
  templateDir: string | undefined,
  port: number = 3000
): Promise<void> {
  const app: Express = express();
  const server: HttpServer = createServer(app);
  const wss = new WebSocketServer({ server });

  wss.on('connection', (ws: WebSocket) => {
    clients.push(ws);
  });

  app.use(express.static(distDir));

  app.get('*', async (req: Request, res: Response) => {
    let requestPath = req.path === '/' ? '/index.html' : req.path;

    if (!requestPath.endsWith('.html')) {
      requestPath += '.html';
    }

    const filePath = path.join(distDir, requestPath);

    try {
      const content = await serveFile(filePath, distDir);
      res.type('text/html').send(content);
    } catch (error) {
      res.status(404).type('text/html').send(
        injectReloadScript(`<!DOCTYPE html>
<html>
<head><title>404 Not Found</title></head>
<body><h1>404 - Page not found</h1></body>
</html>`)
      );
    }
  });

  server.listen(port, () => {
    console.log(`Dev server running at http://localhost:${port}`);
  });

  const watchDirs: string[] = [contentDir];
  if (templateDir) {
    watchDirs.push(templateDir);
  }

  const watcher: FSWatcher = chokidar.watch(watchDirs, {
    ignored: /node_modules/,
    persistent: true
  });

  let rebuildTimeout: NodeJS.Timeout;

  watcher.on('change', () => {
    clearTimeout(rebuildTimeout);
    rebuildTimeout = setTimeout(() => {
      rebuild(contentDir, distDir, templateDir);
    }, 300);
  });

  return new Promise(() => {
    process.on('SIGINT', () => {
      console.log('\nServer stopped');
      watcher.close();
      server.close();
      process.exit(0);
    });
  });
}
