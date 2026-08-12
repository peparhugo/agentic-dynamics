import { Plugin } from '../plugin';
import { MarkdownPlugin } from './markdown';
import { TemplatePlugin } from './template';

export { MarkdownPlugin } from './markdown';
export { TemplatePlugin } from './template';
export { DevServerPlugin } from './dev-server';

export function defaultPlugins(): Plugin[] {
  return [new MarkdownPlugin(), new TemplatePlugin()];
}
