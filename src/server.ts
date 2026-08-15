import { resolve } from 'node:path';
import type { BuildContext } from './plugin';
import { DevServerPlugin, type DevServer, type DevServerOptions } from './plugins/dev-server';

export type { DevServer, DevServerOptions };

export async function startDevServer(options: DevServerOptions = {}): Promise<DevServer> {
  const context: BuildContext = {
    contentDir: resolve(options.contentDir ?? 'content'),
    outputDir: resolve(options.outputDir ?? 'dist'),
    templateDir: resolve(options.templateDir ?? 'templates'),
    pages: [],
  };
  let devServer: DevServer | undefined;
  await new DevServerPlugin(options, (server) => { devServer = server; }).onStart(context);
  if (!devServer) throw new Error('Could not start development server');
  return devServer;
}
