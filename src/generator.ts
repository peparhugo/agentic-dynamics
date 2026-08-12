import { promises as fs } from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';
import type { Plugin, PluginModule, BuildContext, BuildCache, BuildStats, CacheEntry } from './plugin';
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
  incremental?: boolean;
  clean?: boolean;
  onStats?: (stats: BuildStats) => void;
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

async function templateHash(directory: string): Promise<string> {
  const names: string[] = [];
  const visit = async (folder: string, relative = ''): Promise<void> => {
    let entries;
    try { entries = await fs.readdir(path.join(folder, relative), { withFileTypes: true }); } catch { return; }
    for (const entry of entries.sort((a, b) => a.name.localeCompare(b.name))) {
      const name = path.join(relative, entry.name);
      if (entry.isDirectory()) await visit(folder, name);
      else if (entry.isFile() && /\.(hbs|ejs)$/i.test(entry.name)) names.push(`${name}:${await fs.readFile(path.join(folder, name), 'utf8')}`);
    }
  };
  await visit(directory);
  return createHash('sha256').update(names.join('\0')).digest('hex');
}

async function loadCache(filename: string): Promise<BuildCache | undefined> {
  try {
    const value = JSON.parse(await fs.readFile(filename, 'utf8')) as Partial<BuildCache>;
    return value && typeof value.templateHash === 'string' && value.entries && typeof value.entries === 'object'
      ? value as BuildCache
      : undefined;
  } catch { return undefined; }
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[] & { stats: BuildStats }> {
  const contentDir = path.resolve(options.contentDir ?? './content');
  const outputDir = path.resolve(options.outputDir ?? './dist');
  const templatesDir = path.resolve(options.templatesDir ?? './templates');
  const cacheFile = path.join(outputDir, '.ssg-cache.json');
  const previous = options.incremental && !options.clean ? await loadCache(cacheFile) : undefined;
  const currentTemplateHash = await templateHash(templatesDir);
  const cache: BuildCache = previous ?? { entries: {}, templateHash: currentTemplateHash };
  const stats: BuildStats = { pagesBuilt: 0, pagesSkipped: 0, timeSaved: 0 };
  const configPlugins = options.plugins ?? loadConfig(path.resolve(options.configFile ?? 'ssg.config'));
  // Markdown runs first so configured file plugins can transform pages before rendering.
  const plugins = [MarkdownPlugin(), ...configPlugins.map(instantiate), TemplatePlugin()];
  const context: BuildContext = { options, contentDir, outputDir, templatesDir, pages: [], outputs: new Map(), cache, skippedOutputs: new Set(), stats };
  await hook(plugins, 'onStart', context);
  await hook(plugins, 'beforeBuild', context);
  if (!options.incremental || options.clean || !previous) await fs.rm(outputDir, { recursive: true, force: true });
  await fs.mkdir(outputDir, { recursive: true });
  const nextEntries: Record<string, CacheEntry> = {};
  for (let index = 0; index < context.pages.length; index += 1) {
    let page = context.pages[index];
    const source = await fs.readFile(path.join(contentDir, page.sourcePath), 'utf8');
    const sourceHash = createHash('sha256').update(source).digest('hex');
    const old = previous?.entries[page.sourcePath];
    const canSkip = Boolean(previous && previous.templateHash === currentTemplateHash && old?.sourceHash === sourceHash && old.templateHash === currentTemplateHash);
    if (canSkip && old) {
      context.outputs.set(page.outputPath, old.output);
      context.skippedOutputs.add(page.outputPath);
      nextEntries[page.sourcePath] = old;
      stats.pagesSkipped += 1;
      continue;
    }
    for (const plugin of plugins) {
      const replacement = await plugin.onFile?.(page, context);
      if (replacement) { page = replacement; context.pages[index] = page; }
    }
    const output = context.outputs.get(page.outputPath);
    if (output !== undefined) nextEntries[page.sourcePath] = { sourceHash, templateHash: currentTemplateHash, page, output };
    stats.pagesBuilt += 1;
  }
  await hook(plugins, 'afterBuild', context);
  if (previous) {
    for (const sourcePath of Object.keys(previous.entries)) {
      if (!nextEntries[sourcePath]) {
        await fs.rm(path.join(outputDir, previous.entries[sourcePath].page.outputPath), { force: true });
      }
    }
  }
  for (const [relative, output] of context.outputs) {
    const target = path.join(outputDir, relative);
    if (context.skippedOutputs.has(relative)) {
      try { await fs.access(target); continue; } catch { /* restore a missing cached output */ }
    }
    await fs.mkdir(path.dirname(target), { recursive: true });
    await fs.writeFile(target, output);
  }
  await hook(plugins, 'onEnd', context);
  await fs.writeFile(cacheFile, JSON.stringify({ entries: nextEntries, templateHash: currentTemplateHash }, null, 2));
  stats.timeSaved = stats.pagesSkipped;
  options.onStats?.(stats);
  return Object.assign(context.pages, { stats });
}
