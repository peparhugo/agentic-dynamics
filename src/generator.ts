import { promises as fs } from 'node:fs';
import path from 'node:path';
import type { Plugin, PluginModule, BuildContext } from './plugin';
import { MarkdownPlugin, readPages } from './plugins/markdown';
import { TemplatePlugin } from './plugins/template';

export interface Page {
  sourcePath: string;
  outputPath: string;
  title: string;
  date?: string;
  tags: string[];
  html: string;
  template?: string;
  layout?: string;
  frontmatter: Record<string, unknown>;
}

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
  plugins?: PluginModule[];
  configFile?: string;
}

export interface SSGConfig { plugins?: PluginModule[]; }

function loadConfig(filename: string): PluginModule[] {
  const filenames = optionsConfigCandidates(filename);
  for (const candidate of filenames) {
    try {
      // Config files are loaded by the host runtime, so both compiled JS and ts-jest work.
      // eslint-disable-next-line @typescript-eslint/no-var-requires
      const loaded = require(candidate) as SSGConfig | PluginModule[] | { default?: SSGConfig | PluginModule[] };
      const config = 'default' in loaded && loaded.default ? loaded.default : loaded;
      if (Array.isArray(config)) return config;
      return config.plugins ?? [];
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code !== 'MODULE_NOT_FOUND') throw error;
    }
  }
  return [];
}

function optionsConfigCandidates(filename: string): string[] {
  if (path.extname(filename)) return [filename];
  return [filename, `${filename}.ts`, `${filename}.js`];
}

function instantiate(plugin: PluginModule): Plugin {
  return typeof plugin === 'function' ? plugin() : plugin;
}

async function hook(plugins: Plugin[], name: 'onStart' | 'beforeBuild' | 'afterBuild' | 'onEnd', context: BuildContext): Promise<void> {
  for (const plugin of plugins) await plugin[name]?.(context);
}

export async function readPagesFromContent(contentDir: string): Promise<Page[]> { return readPages(contentDir); }
export { readPages };

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const contentDir = path.resolve(options.contentDir ?? './content');
  const outputDir = path.resolve(options.outputDir ?? './dist');
  const templatesDir = path.resolve(options.templatesDir ?? './templates');
  const configPlugins = options.plugins ?? loadConfig(path.resolve(options.configFile ?? 'ssg.config'));
  // Markdown runs first so configured file plugins can transform pages before rendering.
  const plugins = [MarkdownPlugin(), ...configPlugins.map(instantiate), TemplatePlugin()];
  const context: BuildContext = { options, contentDir, outputDir, templatesDir, pages: [], outputs: new Map() };
  await hook(plugins, 'onStart', context);
  await hook(plugins, 'beforeBuild', context);
  await fs.rm(outputDir, { recursive: true, force: true });
  await fs.mkdir(outputDir, { recursive: true });
  for (let index = 0; index < context.pages.length; index += 1) {
    let page = context.pages[index];
    for (const plugin of plugins) {
      const replacement = await plugin.onFile?.(page, context);
      if (replacement) { page = replacement; context.pages[index] = page; }
    }
  }
  await hook(plugins, 'afterBuild', context);
  for (const [relative, output] of context.outputs) {
    const target = path.join(outputDir, relative);
    await fs.mkdir(path.dirname(target), { recursive: true });
    await fs.writeFile(target, output);
  }
  await hook(plugins, 'onEnd', context);
  return context.pages;
}
