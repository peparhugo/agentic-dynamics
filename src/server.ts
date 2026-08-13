import path from 'node:path';
import { createPluginContext } from './plugin';
import { DevServerPlugin, type DevServer, type DevServerOptions } from './plugins/dev-server';

export type { DevServer, DevServerOptions } from './plugins/dev-server';

export async function startDevServer(options: DevServerOptions = {}): Promise<DevServer> {
  const plugin = new DevServerPlugin(options);
  await plugin.onStart(createPluginContext({
    contentDir: path.resolve(options.contentDir ?? 'content'),
    templatesDir: path.resolve(options.templatesDir ?? 'templates'),
    outputDir: path.resolve(options.outputDir ?? 'dist'),
  }));
  return plugin;
}
