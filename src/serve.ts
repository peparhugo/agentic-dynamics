import http from 'http';
import path from 'path';
import { WebSocketServer } from 'ws';
import { FSWatcher } from 'chokidar';
import { SSGEngine } from './engine';
import { loadConfig } from './config';
import { DevServerPlugin } from '../plugins/dev-server';
import { BuildOptions } from './ssg';
import { DEFAULT_SERVE_PORT, LIVE_RELOAD_PATH, injectLiveReload, MIME_TYPES } from './serve-helpers';

export { DEFAULT_SERVE_PORT, LIVE_RELOAD_PATH, injectLiveReload, MIME_TYPES };

export interface ServeOptions extends BuildOptions {
  port?: number;
  host?: string;
}

export interface DevServer {
  server: http.Server;
  wss: WebSocketServer;
  port: number;
  watcher: FSWatcher;
  rebuild: () => void;
  close: () => Promise<void>;
}

/**
 * Start the development server. The DevServerPlugin is added on top of the
 * configured plugins and drives serving, live reload, and rebuilds.
 */
export function startDevServer(options: ServeOptions = {}): DevServer {
  const engine = new SSGEngine(loadConfig(options.configPath));
  const devServerPlugin = new DevServerPlugin(options);
  engine.addPlugin(devServerPlugin);
  devServerPlugin.attach(engine);

  engine.start(options);
  return devServerPlugin.dev;
}
