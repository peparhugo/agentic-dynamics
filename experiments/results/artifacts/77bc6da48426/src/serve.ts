import type { BuildOptions } from './ssg';
import { buildSite } from './ssg';
import { DevServerPlugin, type DevServer } from '../plugins/dev-server';

export interface DevServerOptions extends BuildOptions { port?: number; }
export type { DevServer } from '../plugins/dev-server';

export async function startDevServer(options: DevServerOptions = {}): Promise<DevServer> {
  const plugin = new DevServerPlugin(options.port ?? 3000);
  await buildSite({ ...options, plugins: [...(options.plugins ?? []), plugin] });
  if (!plugin.server) throw new Error('Development server failed to start');
  return plugin.server;
}
