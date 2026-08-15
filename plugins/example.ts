/**
 * Example user plugin.
 *
 * Plugins are TypeScript modules placed under `./plugins/`. A plugin module
 * default-exports an object (or factory function) implementing the `Plugin`
 * interface. It is registered through the `plugins` array in `ssg.config.ts`.
 */

import type { Plugin, PluginContext } from '../src/plugin';

const examplePlugin: Plugin = {
  name: 'example',

  onStart(context: PluginContext): void {
    context.events = context.events ?? [];
    context.events.push('onStart');
  },

  beforeBuild(context: PluginContext): void {
    context.events = context.events ?? [];
    context.events.push('beforeBuild');
  },

  afterBuild(context: PluginContext): void {
    context.events = context.events ?? [];
    context.events.push('afterBuild');
  },

  onFile(_page, context: PluginContext): void {
    context.events = context.events ?? [];
    context.events.push('onFile');
  },

  onEnd(context: PluginContext): void {
    context.events = context.events ?? [];
    context.events.push('onEnd');
  },
};

export default examplePlugin;
