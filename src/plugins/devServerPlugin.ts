import { DevServer, DevServerOptions, startDevServer } from '../devServer';
import { Plugin, PluginContext } from '../plugin';

export interface DevServerPluginOptions {
  /** Port to listen on. Defaults to 3000. Pass 0 to let the OS assign a free port. */
  port?: number;
  /** Called once the server is listening, e.g. to log its port or keep a handle for later shutdown. */
  onServerStart?(server: DevServer): void;
}

/**
 * Built-in plugin that starts the live-reload dev server once a build
 * completes. Only meaningful with `SSGEngine.run()` (the async pipeline),
 * since `startDevServer` itself is async.
 */
export function createDevServerPlugin(options: DevServerPluginOptions = {}): Plugin {
  return {
    name: 'dev-server',
    async onEnd(ctx: PluginContext) {
      const devServerOptions: DevServerOptions = { ...ctx.options, port: options.port };
      const server = await startDevServer(devServerOptions);
      options.onServerStart?.(server);
    },
  };
}
