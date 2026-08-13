import { DevServerPlugin, DevServer, ServeOptions } from './plugins/dev-server';

export { DevServer, ServeOptions } from './plugins/dev-server';

export async function startDevServer(options: ServeOptions = {}): Promise<DevServer> {
  return new DevServerPlugin().start(options);
}
