import { createServer } from 'node:http';
import chokidar, { FSWatcher } from 'chokidar';
import { WebSocketServer } from 'ws';
import { serveFile } from '../src/server';
import type { Plugin, PluginContext } from '../src/plugin';

export function createDevServerPlugin(port = 3000): Plugin {
  let server: ReturnType<typeof createServer> | undefined;
  let watcher: FSWatcher | undefined;
  let webSockets: WebSocketServer | undefined;
  let rebuildTimer: NodeJS.Timeout | undefined;
  return {
    onStart(context: PluginContext) {
      if (context.command !== 'serve') return;
      server = createServer((request, response) => serveFile(request, response, context.options.outputDir));
      webSockets = new WebSocketServer({ noServer: true });
      server.on('upgrade', (request, socket, head) => {
        if (new URL(request.url ?? '/', 'http://localhost').pathname !== '/__ssg_live_reload') return socket.destroy();
        webSockets?.handleUpgrade(request, socket, head, (client) => webSockets?.emit('connection', client, request));
      });
      watcher = chokidar.watch([context.options.contentDir, context.options.templatesDir], { ignoreInitial: true });
      watcher.on('all', () => {
        clearTimeout(rebuildTimer);
        rebuildTimer = setTimeout(() => {
          try {
            const pages = context.rebuild();
            console.log(`Built ${pages.length} page${pages.length === 1 ? '' : 's'}. Reloading browsers.`);
            for (const client of webSockets?.clients ?? []) client.send('reload');
          } catch (error) {
            console.error(error instanceof Error ? error.message : error);
          }
        }, 50);
      });
      const listeningPort = context.options.port ?? port;
      server.listen(listeningPort, 'localhost', () => console.log(`Serving ${context.options.outputDir} at http://localhost:${listeningPort}`));
    },
    async onEnd() {
      clearTimeout(rebuildTimer);
      await watcher?.close();
      for (const client of webSockets?.clients ?? []) client.close();
      if (server?.listening) await new Promise<void>((resolveClose, rejectClose) => server?.close((error) => error ? rejectClose(error) : resolveClose()));
    },
  };
}

export const DevServerPlugin = createDevServerPlugin;
