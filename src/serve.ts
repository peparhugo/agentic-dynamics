import { buildSite } from './index';
import {
  DevServerPlugin,
  RELOAD_MESSAGE,
  LIVE_RELOAD_SCRIPT,
  injectLiveReloadScript,
} from './plugins/dev-server-plugin';
import { DevServer, ServeOptions } from './types';

export { RELOAD_MESSAGE, LIVE_RELOAD_SCRIPT, injectLiveReloadScript };
export type { DevServer, ServeOptions } from './types';

/**
 * Start a live-reload development server.
 *
 * Performs an initial build, serves the generated site from outputDir over
 * HTTP, injects a WebSocket client script into HTML responses, watches the
 * content and templates directories for changes, rebuilds on change, and tells
 * connected browsers to reload when a rebuild completes.
 */
export async function startDevServer(options: ServeOptions = {}): Promise<DevServer> {
  const plugin = new DevServerPlugin(buildSite, options);
  return plugin.start();
}
