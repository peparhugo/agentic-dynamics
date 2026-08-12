import { buildSite, BuildOptions } from './generator';
import { DevServerPlugin, ServeOptions, DevServer } from '../plugins/dev-server';

export type { ServeOptions, DevServer } from '../plugins/dev-server';

export function startDevServer(options: ServeOptions = {}): Promise<DevServer> {
  const plugin = new DevServerPlugin();
  return plugin.start(options, () => buildSite({ ...options } as BuildOptions));
}
