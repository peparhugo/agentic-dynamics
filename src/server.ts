export { DevServer, ServeOptions } from './plugins/dev-server';
import { DevServer, DevServerPlugin, ServeOptions } from './plugins/dev-server';

export async function startDevServer(options: ServeOptions = {}): Promise<DevServer> {
  return new DevServerPlugin().start(options);
}
