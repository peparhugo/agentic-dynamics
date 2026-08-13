import { createEngine } from './index';
import { DevServerPlugin } from './plugins/dev-server';
import type { BuildOptions } from './types';

export interface ServeOptions extends BuildOptions {
  port?: number;
}

export interface DevelopmentServer {
  port: number;
  close(): Promise<void>;
}

export { DevServerPlugin } from './plugins/dev-server';

export async function startDevelopmentServer(options: ServeOptions = {}): Promise<DevelopmentServer> {
  const plugin = new DevServerPlugin(options.port ?? 3000);
  const engine = await createEngine(options, [plugin]);
  try {
    await engine.start();
    await engine.build();
  } catch (error) {
    await engine.end();
    throw error;
  }
  return { port: plugin.port, close: () => engine.end() };
}
