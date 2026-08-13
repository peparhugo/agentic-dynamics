import { SsgEngine } from './engine';
import { BuildOptions, BuildStats, Page, Plugin, PluginContext, PluginPage, SsgConfig } from './plugin';

export { SsgEngine } from './engine';
export { MarkdownPlugin } from './plugins/markdown';
export { TemplatePlugin } from './plugins/template';
export { DevServerPlugin } from './server';
export { BuildOptions, BuildStats, Page, Plugin, PluginContext, PluginPage, SsgConfig } from './plugin';

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const engine = new SsgEngine(options);
  try {
    return await engine.build();
  } finally {
    await engine.stop();
  }
}
