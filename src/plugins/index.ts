import { MarkdownPlugin } from './markdown-plugin';
import { TemplatePlugin } from './template-plugin';
import { DevServerPlugin } from './dev-server-plugin';
import type { Plugin } from './types';

/**
 * The built-in plugin set. Markdown parsing and template rendering always
 * participate; the dev server plugin is only registered for the `serve`
 * command.
 */
export function defaultPlugins(command: 'build' | 'serve' = 'build'): Plugin[] {
  const plugins: Plugin[] = [new MarkdownPlugin(), new TemplatePlugin()];
  if (command === 'serve') {
    plugins.push(new DevServerPlugin());
  }
  return plugins;
}
