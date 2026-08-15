import { Plugin, PluginContext } from '../src/plugin';
import { Page } from '../src/types';

/**
 * Example user plugin. Plugins live in ./plugins and are loaded from
 * ssg.config.ts via the `plugins` array. A plugin implements any subset of
 * the lifecycle hooks: onStart, beforeBuild, afterBuild, onFile, onEnd.
 */
const examplePlugin: Plugin = {
  name: 'example',

  onStart(context: PluginContext): void {
    context.exampleStartedAt = Date.now();
  },

  onFile(page: Page, _context: PluginContext): Page {
    return page;
  },

  onEnd(context: PluginContext): void {
    delete context.exampleStartedAt;
  },
};

export default examplePlugin;
