import type { BuildOptions } from './generator.js';
import { DevServerPlugin, type DevServer } from './plugins/dev-server.js';

export type { DevServer } from './plugins/dev-server.js';

export async function startDevServer(options: BuildOptions & { port?: number } = {}): Promise<DevServer> {
  const plugin = new DevServerPlugin(options);
  await plugin.onStart();
  return plugin.devServer;
}
