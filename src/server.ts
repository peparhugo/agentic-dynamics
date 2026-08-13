import { DevServerPlugin, type DevelopmentServer, type ServeOptions } from './plugins/dev-server.js';

export type { DevelopmentServer, ServeOptions };

export async function startDevelopmentServer(options: ServeOptions = {}): Promise<DevelopmentServer> {
  return new DevServerPlugin().start(options);
}
