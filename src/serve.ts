import { SiteEngine } from './engine';
import {
  DEFAULT_PORT,
  LIVERELOAD_PATH,
  RELOAD_MESSAGE,
  REBUILD_DELAY_MS,
  ServeOptions,
  ServeHandle,
  DevServerPlugin,
  clientScript,
  hasLiveReload,
  injectLiveReload,
  createRequestHandler,
  broadcastReload,
} from './plugins/devServer';

export {
  DEFAULT_PORT,
  LIVERELOAD_PATH,
  RELOAD_MESSAGE,
  REBUILD_DELAY_MS,
  DevServerPlugin,
  clientScript,
  hasLiveReload,
  injectLiveReload,
  createRequestHandler,
  broadcastReload,
};
export type { ServeOptions, ServeHandle };

export function serve(options: ServeOptions): ServeHandle {
  const engine = new SiteEngine({
    contentDir: options.contentDir,
    outputDir: options.outputDir,
    templatesDir: options.templatesDir,
    devServer: true,
  });
  return engine.serve(options);
}
