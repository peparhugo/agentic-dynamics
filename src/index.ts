import { SsgEngine } from './engine';
import { MarkdownPlugin } from './plugins/markdown';
import type { BuildOptions, Page } from './types';

export function parseMarkdown(source: string, relativePath: string): Page {
  return new MarkdownPlugin().parse(source, relativePath);
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  return new SsgEngine(options).build();
}

export { SsgEngine } from './engine';
export { loadPlugins } from './config';
export { MarkdownPlugin } from './plugins/markdown';
export { TemplatePlugin, renderPage, renderIndex } from './plugins/template';
export { DevServerPlugin } from './plugins/dev-server';
export type { BuildContext, BuildOptions, BuildStats, Frontmatter, Page, Plugin, SsgConfig } from './types';
export { startDevServer, type DevServer, type ServeOptions } from './server';
