/**
 * Development server API surface.
 *
 * The implementation lives in `./plugins/dev-server` (the built-in
 * DevServerPlugin); this module re-exports it so the public API stays
 * unchanged.
 */

export {
  DEFAULT_PORT,
  DEV_SERVER_PLUGIN_NAME,
  DevServerPlugin,
  RELOAD_PATH,
  REBUILD_DELAY_MS,
  injectLiveReloadScript,
  startDevServer,
} from './plugins/dev-server';
export type { DevServer, ServeOptions } from './plugins/dev-server';
