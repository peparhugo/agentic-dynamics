import { createDevServer, ServeOptions, DevServer } from './plugins/server';

export {
  ServeOptions,
  DevServer,
  LIVE_RELOAD_PATH,
  injectLiveReloadScript,
  DevServerPlugin,
} from './plugins/server';

export function startServer(options: ServeOptions): DevServer {
  return createDevServer(options);
}
