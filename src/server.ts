import { DevServerPlugin, injectReloadScript } from './plugins/dev-server';
import type { ServeOptions, DevServer } from './plugins/dev-server';

export { DevServerPlugin, injectReloadScript };
export type { ServeOptions, DevServer };

export async function serveSite(options: ServeOptions): Promise<DevServer> {
  return new DevServerPlugin().serve(options);
}
