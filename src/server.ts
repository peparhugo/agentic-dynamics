import { DevServerPlugin, type DevelopmentServer, type ServeOptions } from './plugins/dev-server.js';

export type { DevelopmentServer, ServeOptions } from './plugins/dev-server.js';

export async function serveSite(options: ServeOptions = {}): Promise<DevelopmentServer> {
  return new DevServerPlugin().start(options);
}
