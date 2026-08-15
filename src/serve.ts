import * as path from 'path';
import chokidar from 'chokidar';
import { DevServerPlugin, injectLiveReload, LIVERELOAD_PATH } from '../plugins/dev-server-plugin';
import { loadConfig } from './config';
import { buildSite, BuildOptions } from './site';

export { injectLiveReload, LIVERELOAD_PATH };

export interface ServeOptions extends BuildOptions {
  port?: number;
}

export interface DevServer {
  url: string;
  port: number;
  close: () => Promise<void>;
}

const REBUILD_DEBOUNCE_MS = 50;

export function startDevServer(options: ServeOptions): Promise<DevServer> {
  const contentDir = path.resolve(options.contentDir);
  const outputDir = path.resolve(options.outputDir);
  const templatesDir = path.resolve(options.templatesDir ?? './templates');
  const requestedPort = options.port ?? 3000;

  const basePlugins = options.plugins ?? loadConfig(options.configPath).plugins;
  const devServerPlugin = new DevServerPlugin(outputDir);
  const plugins = [...basePlugins, devServerPlugin];

  const rebuild = (): void => {
    buildSite({ contentDir, outputDir, templatesDir, plugins });
  };

  rebuild();

  const listening = devServerPlugin.listen(requestedPort);

  let rebuildTimer: ReturnType<typeof setTimeout> | null = null;
  const scheduleRebuild = (): void => {
    if (rebuildTimer) clearTimeout(rebuildTimer);
    rebuildTimer = setTimeout(() => {
      rebuildTimer = null;
      try {
        rebuild();
      } catch (err) {
        // eslint-disable-next-line no-console
        console.error('Rebuild failed:', err instanceof Error ? err.message : err);
      }
    }, REBUILD_DEBOUNCE_MS);
  };

  const watcher = chokidar.watch([contentDir, templatesDir], { ignoreInitial: true });
  watcher.on('all', scheduleRebuild);

  const watcherReady = new Promise<void>((resolveReady) => watcher.once('ready', () => resolveReady()));

  return Promise.all([listening, watcherReady]).then(([{ port: actualPort }]) => ({
    url: `http://localhost:${actualPort}`,
    port: actualPort,
    close: () =>
      new Promise<void>((resolveClose) => {
        if (rebuildTimer) clearTimeout(rebuildTimer);
        watcher.close().then(() => {
          devServerPlugin.close().then(() => resolveClose());
        });
      }),
  }));
}
