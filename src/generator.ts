import { promises as fs } from 'node:fs';
import path from 'node:path';
import matter from 'gray-matter';
import type { Plugin, PluginModule, PluginContext } from './plugin';
import { MarkdownPlugin } from './markdown-plugin';
import { TemplatePlugin } from './template-plugin';

export type { Plugin, PluginContext, PluginModule } from './plugin';
export { MarkdownPlugin } from './markdown-plugin';
export { TemplatePlugin } from './template-plugin';
export { DevServerPlugin } from './dev-server-plugin';

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
  config?: string;
  plugins?: PluginModule[];
}

export interface Page {
  title: string;
  date?: string;
  tags: string[];
  html: string;
  sourcePath: string;
  outputPath: string;
}

async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files: string[] = [];
  for (const entry of entries) {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) files.push(...await markdownFiles(entryPath));
    else if (entry.isFile() && /\.(md|markdown)$/i.test(entry.name)) files.push(entryPath);
  }
  return files.sort();
}

const outputName = (relativePath: string): string => relativePath.replace(/\.(md|markdown)$/i, '.html');

async function loadConfiguredPlugins(options: BuildOptions): Promise<Plugin[]> {
  const configured = options.plugins ?? [];
  const configPath = path.resolve(options.config ?? 'ssg.config.ts');
  let configPlugins: PluginModule[] = [];
  try {
    // require keeps this compatible with both ts-jest and compiled CommonJS projects.
    const loaded = require(configPath) as { default?: { plugins?: PluginModule[] } | PluginModule[]; plugins?: PluginModule[] };
    const value = loaded.default ?? loaded.plugins ?? [];
    configPlugins = Array.isArray(value) ? value : value.plugins ?? [];
  } catch (error: unknown) {
    if ((error as NodeJS.ErrnoException).code !== 'MODULE_NOT_FOUND') throw error;
  }
  const modules = [...configured, ...configPlugins];
  const result: Plugin[] = [];
  for (const module of modules) result.push(typeof module === 'function' ? await module() : module);
  return result;
}

const runHook = async (plugins: Plugin[], hook: keyof Plugin, context: PluginContext): Promise<void> => {
  for (const plugin of plugins) {
    const callback = plugin[hook];
    if (callback) await (callback as (context: PluginContext) => void | Promise<void>)(context);
  }
};

const runFileHook = async (plugins: Plugin[], page: Page, context: PluginContext): Promise<void> => {
  for (const plugin of plugins) if (plugin.onFile) await plugin.onFile(page, context);
};

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const normalized: BuildOptions = {
    ...options,
    contentDir: path.resolve(options.contentDir ?? './content'),
    outputDir: path.resolve(options.outputDir ?? './dist'),
    templatesDir: path.resolve(options.templatesDir ?? './templates'),
  };
  const pages: Page[] = [];
  const context: PluginContext = { options: normalized, pages };
  const plugins = [MarkdownPlugin, TemplatePlugin, ...(await loadConfiguredPlugins(normalized))];
  await runHook(plugins, 'onStart', context);
  await runHook(plugins, 'beforeBuild', context);
  for (const sourcePath of await markdownFiles(normalized.contentDir!)) {
    const relativePath = path.relative(normalized.contentDir!, sourcePath).split(path.sep).join('/');
    const parsed = matter(await fs.readFile(sourcePath, 'utf8'));
    const page: Page = {
      title: typeof parsed.data.title === 'string' && parsed.data.title.trim() ? parsed.data.title : path.basename(relativePath, path.extname(relativePath)),
      tags: [],
      html: parsed.content,
      sourcePath,
      outputPath: outputName(relativePath),
    };
    pages.push(page);
    await runFileHook(plugins, page, context);
  }
  pages.sort((a, b) => (b.date ?? '').localeCompare(a.date ?? '') || a.outputPath.localeCompare(b.outputPath));
  await fs.rm(normalized.outputDir!, { recursive: true, force: true });
  await fs.mkdir(normalized.outputDir!, { recursive: true });
  await runHook(plugins, 'afterBuild', context);
  await runHook(plugins, 'onEnd', context);
  return pages;
}
