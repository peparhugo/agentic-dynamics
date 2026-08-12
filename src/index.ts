import { promises as fs } from 'node:fs';
import path from 'node:path';
import { MarkdownPlugin, parseMarkdown } from './plugins/markdown';
import { TemplatePlugin } from './plugins/template';
import { BuildContext, Plugin, PluginModule } from './plugin';

export interface Page { title: string; date?: string; tags: string[]; slug: string; html: string; sourcePath: string; template?: string; layout?: string; data?: Record<string, unknown>; }
export interface BuildOptions { contentDir?: string; outputDir?: string; templatesDir?: string; defaultTemplate?: string; config?: string; plugins?: PluginModule[]; }
export { Plugin, BuildContext } from './plugin';
export { MarkdownPlugin, parseMarkdown } from './plugins/markdown';
export { TemplatePlugin } from './plugins/template';
export { DevServerPlugin } from './plugins/dev-server';

async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await fs.readdir(directory, { withFileTypes: true }); const files: string[] = [];
  for (const entry of entries) { const full = path.join(directory, entry.name); if (entry.isDirectory()) files.push(...await markdownFiles(full)); else if (/\.md$/i.test(entry.name)) files.push(full); }
  return files.sort();
}

function resolvePlugin(module: PluginModule): Plugin {
  const value = typeof module === 'object' && module !== null && 'default' in module ? module.default : module;
  return typeof value === 'function' ? value() : value;
}

export function defineConfig(config: { plugins?: PluginModule[] }): { plugins: PluginModule[] } {
  return { plugins: config.plugins ?? [] };
}

async function loadConfiguredPlugins(options: BuildOptions): Promise<Plugin[]> {
  if (options.plugins) return options.plugins.map(resolvePlugin);
  const configured = options.config ?? path.resolve('./ssg.config.ts');
  try {
    // TypeScript configs are directly loadable in ts-jest and ts-node based CLI environments.
    const loaded = require(configured) as { default?: PluginModule[] | PluginModule | { plugins?: PluginModule[] }; plugins?: PluginModule[] | PluginModule };
    const exported = loaded.default ?? loaded;
    const value = typeof exported === 'object' && exported !== null && 'plugins' in exported
      ? exported.plugins ?? [] : exported;
    return (Array.isArray(value) ? value : [value]).map(resolvePlugin);
  } catch (error: unknown) {
    if ((error as NodeJS.ErrnoException).code === 'MODULE_NOT_FOUND') return [];
    throw error;
  }
}

async function hook(plugins: Plugin[], name: 'onStart' | 'beforeBuild' | 'afterBuild' | 'onEnd', context: BuildContext): Promise<void> {
  for (const plugin of plugins) if (plugin[name]) await plugin[name]!(context);
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const resolved: Required<BuildOptions> = {
    contentDir: path.resolve(options.contentDir ?? './content'), outputDir: path.resolve(options.outputDir ?? './dist'),
    templatesDir: path.resolve(options.templatesDir ?? './templates'), defaultTemplate: options.defaultTemplate ?? 'default',
    config: options.config ?? path.resolve('./ssg.config.ts'), plugins: options.plugins ?? []
  };
  const plugins = [new MarkdownPlugin(), new TemplatePlugin(), ...(await loadConfiguredPlugins(options))];
  const files = await markdownFiles(resolved.contentDir);
  const context: BuildContext = { options: resolved, contentDir: resolved.contentDir, outputDir: resolved.outputDir, templatesDir: resolved.templatesDir, files, pages: [] };
  await hook(plugins, 'onStart', context); await hook(plugins, 'beforeBuild', context);
  const markdown = plugins.find((plugin): plugin is MarkdownPlugin => plugin instanceof MarkdownPlugin) ?? new MarkdownPlugin();
  context.pages = await Promise.all(files.map(async (file) => { const relative = path.relative(resolved.contentDir, file); const page = await markdown.parse(await fs.readFile(file, 'utf8'), relative); page.slug = `${relative.replace(/\.md$/i, '')}.html`; page.sourcePath = relative; return page; }));
  for (let index = 0; index < context.pages.length; index += 1) for (const plugin of plugins) if (plugin.onFile) { const result = await plugin.onFile(context.pages[index], context); if (result) context.pages[index] = result; }
  await fs.rm(resolved.outputDir, { recursive: true, force: true }); await fs.mkdir(resolved.outputDir, { recursive: true });
  try { await hook(plugins, 'afterBuild', context); } finally { await hook(plugins, 'onEnd', context); }
  return context.pages;
}
