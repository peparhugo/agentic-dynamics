import { DevServerPlugin, type DevServer, type ServeOptions } from './plugins/dev-server';

export async function startDevServer(options: ServeOptions = {}): Promise<DevServer> {
  return new DevServerPlugin().start(options);
}

export type { DevServer, ServeOptions };
