import { SSGEngine } from './core';
import { loadPluginsFromConfig } from './config';
import { DevServerPlugin } from './plugins/DevServerPlugin';
import type { Server } from 'http';
import type { FSWatcher } from 'chokidar';
import type { WebSocketServer } from 'ws';
import type { SiteBuildResult } from './build';

export const DEFAULT_PORT = 3000;
export const RELOAD_PATH = '/__ssg_reload';
export const RELOAD_MESSAGE = 'reload';

export { injectReloadScript } from './plugins/DevServerPlugin';

export interface DevServerOptions {
  port?: number;
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
  onBuild?: (result: SiteBuildResult) => void;
  onError?: (err: Error) => void;
}

export interface DevServer {
  port: number;
  outputDir: string;
  server: Server;
  ws: WebSocketServer;
  watcher: FSWatcher;
  close: () => Promise<void>;
}

export function startDevServer(options: DevServerOptions = {}): DevServer {
  const port = options.port ?? DEFAULT_PORT;
  const contentDir = options.contentDir ?? 'content';
  const outputDir = options.outputDir ?? 'dist';
  const templatesDir = options.templatesDir ?? 'templates';

  const devServerPlugin = new DevServerPlugin();
  const plugins = [
    ...loadPluginsFromConfig().filter((plugin) => plugin.name !== devServerPlugin.name),
    devServerPlugin,
  ];

  const engine = new SSGEngine({ contentDir, outputDir, templatesDir, plugins });
  engine.ctx.port = port;
  engine.ctx.onBuild = (result) => {
    if (options.onBuild) {
      options.onBuild(result);
    }
  };
  engine.ctx.onError = (err) => {
    if (options.onError) {
      options.onError(err);
    } else {
      process.stderr.write(`ssg serve: ${err.message}\n`);
    }
  };

  engine.start();

  try {
    engine.build();
  } catch (err) {
    const error = err instanceof Error ? err : new Error(String(err));
    if (options.onError) {
      options.onError(error);
    } else {
      process.stderr.write(`ssg serve: ${error.message}\n`);
    }
  }

  return {
    port: devServerPlugin.port,
    outputDir,
    server: devServerPlugin.server as Server,
    ws: devServerPlugin.ws as WebSocketServer,
    watcher: devServerPlugin.watcher as FSWatcher,
    close: async () => {
      engine.stop();
    },
  };
}
