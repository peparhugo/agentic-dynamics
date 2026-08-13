import { loadPlugins } from './config.js';
import { SsgEngine } from './engine.js';
import { MarkdownPlugin } from './plugins/markdown.js';
import { TemplatePlugin } from './plugins/template.js';
import type { BuildOptions, Page, Plugin } from './plugin.js';

export type { BuildContext, BuildOptions, BuildPage, Page, Plugin, SsgConfig } from './plugin.js';
export { defineConfig } from './plugin.js';
export { SsgEngine } from './engine.js';
export { MarkdownPlugin } from './plugins/markdown.js';
export { TemplatePlugin } from './plugins/template.js';
export { DevServerPlugin } from './plugins/dev-server.js';

export function createBuildPlugins(options: BuildOptions = {}): Plugin[] {
  return [new MarkdownPlugin(), ...loadPlugins(options.configFile), ...(options.plugins ?? []), new TemplatePlugin()];
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const engine = new SsgEngine(options, createBuildPlugins(options));
  try {
    return await engine.build();
  } finally {
    await engine.end();
  }
}
