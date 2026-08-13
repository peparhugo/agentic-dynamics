import { DevServerPlugin, DevelopmentServer } from './plugins/dev-server';
import { BuildOptions } from './site';

export interface ServeOptions extends BuildOptions { port?: number; }
export type { DevelopmentServer };

export function startDevelopmentServer(options: ServeOptions = {}): DevelopmentServer {
  return new DevServerPlugin().start(options);
}
