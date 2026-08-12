import { SSG } from './engine';
import { builtinPlugins, createDevServerPlugin } from './plugins';
import { DevServer, DevServerOptions } from './plugins/dev-server';

export { liveReloadScript, injectLiveReload } from './plugins/dev-server';
export type { DevServer, DevServerOptions } from './plugins/dev-server';

export function startDevServer(options: DevServerOptions): DevServer {
  const dev = createDevServerPlugin({ host: options.host, port: options.port });
  const engine = new SSG({
    options: {
      contentDir: options.contentDir,
      outputDir: options.outputDir,
      templatesDir: options.templatesDir,
    },
    plugins: [...builtinPlugins(), dev.plugin],
  });
  engine.start();

  try {
    const pages = engine.build();
    console.log(`Built ${pages.length} page${pages.length === 1 ? '' : 's'} into ${options.outputDir}`);
  } catch (err) {
    console.error(`Initial build failed: ${(err as Error).message}`);
  }

  return dev.getDevServer();
}
