export { DevServerPlugin } from './plugins/dev-server';
export { DevelopmentServer, ServeOptions } from './plugins/dev-server';
import { DevServerPlugin, ServeOptions, DevelopmentServer } from './plugins/dev-server';

/** Backwards-compatible development server entry point. */
export function serveSite(options: ServeOptions = {}): Promise<DevelopmentServer> {
  return DevServerPlugin.serve(options);
}
