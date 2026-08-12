import { Plugin } from '../plugin';
import { markdownPlugin } from './markdown';
import { createTemplatePlugin } from './template';

export { markdownPlugin } from './markdown';
export { createTemplatePlugin } from './template';
export {
  createDevServerPlugin,
  liveReloadScript,
  injectLiveReload,
} from './dev-server';
export type {
  DevServer,
  DevServerOptions,
  DevServerPluginInstance,
} from './dev-server';

export function builtinPlugins(): Plugin[] {
  return [markdownPlugin, createTemplatePlugin()];
}
