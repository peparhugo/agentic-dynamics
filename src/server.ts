import { DevServerPlugin, type DevServer, type ServeOptions } from './plugins/dev-server';

export type { DevServer, ServeOptions } from './plugins/dev-server';
export { DevServerPlugin } from './plugins/dev-server';

/** Build the site and start a live-reloading development server. */
export async function startDevServer(options: ServeOptions = {}): Promise<DevServer> {
  return new DevServerPlugin().start(options);
}
