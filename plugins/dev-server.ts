import { startDevServer } from '../src/server';
import { Plugin } from '../src/types';

/** Exposes live-reload development serving as a plugin for programmatic use. */
export function DevServerPlugin(): Plugin {
  return {
    async onStart(context) {
      await startDevServer({
        contentDirectory: context.contentDirectory,
        outputDirectory: context.outputDirectory,
        templatesDirectory: context.templatesDirectory,
      });
    },
  };
}

export default DevServerPlugin;
