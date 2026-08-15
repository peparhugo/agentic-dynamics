import { Plugin, PluginContext } from '../plugin';
import { PageData } from '../page';
import express, { Express, Request, Response } from 'express';
import path from 'path';
import { WebSocketServer, WebSocket } from 'ws';
import { createServer, Server as HttpServer } from 'http';
import chokidar, { FSWatcher } from 'chokidar';
import { promises as fs } from 'fs';

interface DevServerConfig {
  port: number;
  onRebuild?: () => Promise<void>;
}

let devServerConfig: DevServerConfig | null = null;
let clients: WebSocket[] = [];
let server: HttpServer | null = null;
let watcher: FSWatcher | null = null;

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

async function serveFile(filePath: string): Promise<string> {
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

export function createDevServerPlugin(config: DevServerConfig): Plugin {
  return {
    name: 'dev-server',

    onStart: async (context: PluginContext): Promise<void> => {
      devServerConfig = config;

      const app: Express = express();
      server = createServer(app);
      const wss = new WebSocketServer({ server });

      wss.on('connection', (ws: WebSocket) => {
        clients.push(ws);
      });

      app.use(express.static(context.outputDir));

      app.get('*', async (req: Request, res: Response) => {
        let requestPath = req.path === '/' ? '/index.html' : req.path;

        if (!requestPath.endsWith('.html')) {
          requestPath += '.html';
        }

        const filePath = path.join(context.outputDir, requestPath);

        try {
          const content = await serveFile(filePath);
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

      server.listen(config.port, () => {
        console.log(`Dev server running at http://localhost:${config.port}`);
      });

      const watchDirs: string[] = [context.contentDir];
      if (context.templateDir) {
        watchDirs.push(context.templateDir);
      }

      watcher = chokidar.watch(watchDirs, {
        ignored: /node_modules/,
        persistent: true
      });

      let rebuildTimeout: NodeJS.Timeout;

      watcher.on('change', () => {
        clearTimeout(rebuildTimeout);
        rebuildTimeout = setTimeout(async () => {
          if (config.onRebuild) {
            await config.onRebuild();
          }
          console.log('Build complete, reloading browser...');
          broadcastReload();
        }, 300);
      });
    },

    onEnd: async (_context: PluginContext): Promise<void> => {
      if (watcher) {
        await watcher.close();
      }
      if (server) {
        server.close();
      }
    },

    onFile: async (page: PageData, _context: PluginContext): Promise<PageData> => {
      return page;
    }
  };
}
