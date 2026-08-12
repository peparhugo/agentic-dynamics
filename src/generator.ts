import { promises as fs } from 'node:fs';
import path from 'node:path';
import { MarkdownPlugin } from './markdown-plugin';
import { TemplatePlugin } from './template-plugin';
import type { Plugin, PluginContext, PluginModule } from './plugin';

export interface SiteOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
  plugins?: Plugin[];
  configFile?: string;
}

export interface Page {
  source: string;
  output: string;
  title: string;
  date?: string;
  tags: string[];
  html: string;
  template?: string;
  layout?: string;
}

export interface SsgConfig { plugins?: PluginModule[]; }

async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files: string[] = [];
  for (const entry of entries) {
    const file = path.join(directory, entry.name);
    if (entry.isDirectory()) files.push(...await markdownFiles(file));
    else if (entry.isFile() && /\.md$/i.test(entry.name)) files.push(file);
  }
  return files.sort((a, b) => a.localeCompare(b));
}

function resolveModule(module: PluginModule): Plugin[] {
  if (Array.isArray(module)) return module.flatMap(resolveModule as (value: unknown) => Plugin[]);
  const value = module as PluginModule & { default?: PluginModule; plugins?: Plugin[] };
  if (value && typeof value === 'object' && value.plugins) return value.plugins;
  const candidate = value && typeof value === 'object' && 'default' in value ? value.default : value;
  if (typeof candidate === 'function') return [candidate()];
  return candidate ? [candidate as Plugin] : [];
}

function configuredPlugins(options: SiteOptions): Plugin[] {
  const file = options.configFile ?? path.resolve(process.cwd(), 'ssg.config.ts');
  let config: SsgConfig | undefined;
  try {
    // require is intentional: it supports compiled JS configs and ts-jest's TS configs.
    const loaded = require(file) as SsgConfig & { default?: SsgConfig };
    config = loaded.default ?? loaded;
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== 'MODULE_NOT_FOUND') throw error;
  }
  return (config?.plugins ?? []).flatMap(resolveModule);
}

async function hooks(plugins: Plugin[], name: 'onStart' | 'beforeBuild' | 'afterBuild' | 'onEnd', context: PluginContext): Promise<void> {
  for (const plugin of plugins) if (plugin[name]) await plugin[name]!(context);
}

export async function buildSite(options: SiteOptions = {}): Promise<Page[]> {
  const contentDir = path.resolve(options.contentDir ?? './content');
  const outputDir = path.resolve(options.outputDir ?? './dist');
  const templatesDir = path.resolve(options.templatesDir ?? './templates');
  const plugins = [new MarkdownPlugin(), new TemplatePlugin(), ...configuredPlugins(options), ...(options.plugins ?? [])];
  const pages: Page[] = [];
  const context: PluginContext = { options, contentDir, outputDir, templatesDir, pages };

  await hooks(plugins, 'onStart', context);
  await fs.rm(outputDir, { recursive: true, force: true });
  await fs.mkdir(outputDir, { recursive: true });
  await hooks(plugins, 'beforeBuild', context);

  for (const file of await markdownFiles(contentDir)) {
    const relative = path.relative(contentDir, file);
    let page: Page = { source: relative, output: relative.replace(/\.md$/i, '.html'), title: path.basename(relative, path.extname(relative)), tags: [], html: '' };
    Object.defineProperty(page, 'filePath', { value: file, enumerable: false, writable: true });
    for (const plugin of plugins) if (plugin.onFile) page = (await plugin.onFile(page, context)) ?? page;
    pages.push(page);
    const destination = path.join(outputDir, page.output);
    await fs.mkdir(path.dirname(destination), { recursive: true });
    await fs.writeFile(destination, page.html, 'utf8');
  }

  await hooks(plugins, 'afterBuild', context);
  await hooks(plugins, 'onEnd', context);
  return pages;
}

export { MarkdownPlugin } from './markdown-plugin';
export { TemplatePlugin } from './template-plugin';
export type { Plugin, PluginContext, PluginModule } from './plugin';
