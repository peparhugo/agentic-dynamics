import { SSGEngine } from './engine';
import { loadPlugins, type Plugin } from './plugin';
import { MarkdownPlugin } from './plugins/markdown';
import { TemplatePlugin } from './plugins/template';
import type { BuildOptions, Page } from './types';

export type { BuildOptions, BuildStats, Frontmatter, Page } from './types';
export type { Plugin, PluginContext, SsgConfig } from './plugin';
export { SSGEngine } from './engine';
export { MarkdownPlugin } from './plugins/markdown';
export { TemplatePlugin } from './plugins/template';
export { DevServerPlugin } from './plugins/dev-server';

export async function createEngine(options: BuildOptions = {}, additionalPlugins: Plugin[] = []): Promise<SSGEngine> {
  const configured = await loadPlugins(options);
  return new SSGEngine(options, [new MarkdownPlugin(), ...configured, new TemplatePlugin(), ...additionalPlugins]);
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const engine = await createEngine(options);
  try {
    await engine.start();
    return await engine.build();
  } finally {
    await engine.end();
  }
}
