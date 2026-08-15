import path from 'node:path';
import { BuildOptions, SSG } from './generator';
import DevServerPlugin, { DevServer } from './plugins/dev-server';

export interface ServeOptions extends BuildOptions { port?: number }
export type { DevServer } from './plugins/dev-server';

export async function startDevServer(options: ServeOptions = {}): Promise<DevServer> {
  const plugin = new DevServerPlugin({ port: options.port });
  const generator = new SSG(options, [plugin]);
  await generator.build();
  if (!plugin.server) throw new Error('Dev server failed to start');
  return plugin.server;
}

export async function serveSite(options: ServeOptions = {}): Promise<void> {
  const instance = await startDevServer(options);
  const address = instance.server.address();
  const port = typeof address === 'object' && address ? address.port : options.port ?? 3000;
  console.log(`Serving ${path.resolve(options.outputDir ?? './dist')} at http://localhost:${port}`);
}
