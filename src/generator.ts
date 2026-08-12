import { promises as fs } from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';
import matter from 'gray-matter';
import type { Plugin, PluginModule, PluginContext } from './plugin';
import { MarkdownPlugin, setParsedPageData, type Frontmatter } from './markdown-plugin';
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
  incremental?: boolean;
  clean?: boolean;
}

export interface BuildStats {
  pagesBuilt: number;
  pagesSkipped: number;
  timeSaved: number;
}

export type BuildPages = Page[] & { stats: BuildStats };

interface CachePage {
  sourceHash: string;
  templateHash: string;
  data: Frontmatter;
  content: string;
  html: string;
  outputPath: string;
}

interface BuildCache {
  version: 1;
  templatesHash: string;
  pages: Record<string, CachePage>;
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

const hash = (value: string): string => createHash('sha256').update(value).digest('hex');

async function templateHash(directory: string): Promise<string> {
  const files: string[] = [];
  async function visit(current: string): Promise<void> {
    let entries: import('node:fs').Dirent[];
    try { entries = await fs.readdir(current, { withFileTypes: true }); } catch { return; }
    for (const entry of entries.sort((a, b) => a.name.localeCompare(b.name))) {
      const file = path.join(current, entry.name);
      if (entry.isDirectory()) await visit(file);
      else if (entry.isFile() && /\.(hbs|ejs)$/i.test(entry.name)) files.push(`${path.relative(directory, file)}\0${await fs.readFile(file, 'utf8')}`);
    }
  }
  await visit(directory);
  return hash(files.join('\0'));
}

async function readCache(file: string): Promise<BuildCache | undefined> {
  try {
    const value = JSON.parse(await fs.readFile(file, 'utf8')) as BuildCache;
    return value?.version === 1 && value.pages ? value : undefined;
  } catch { return undefined; }
}

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

export async function buildSite(options: BuildOptions = {}): Promise<BuildPages> {
  const normalized: BuildOptions = {
    ...options,
    contentDir: path.resolve(options.contentDir ?? './content'),
    outputDir: path.resolve(options.outputDir ?? './dist'),
    templatesDir: path.resolve(options.templatesDir ?? './templates'),
  };
  const pages: Page[] = [];
  const stats: BuildStats = { pagesBuilt: 0, pagesSkipped: 0, timeSaved: 0 };
  const cacheFile = path.join(path.dirname(normalized.outputDir!), '.ssg-cache.json');
  const templatesHash = await templateHash(normalized.templatesDir!);
  const oldCache = normalized.incremental && !normalized.clean ? await readCache(cacheFile) : undefined;
  const cache = oldCache && oldCache.templatesHash === templatesHash ? oldCache : undefined;
  const changedOutputs = new Set<string>();
  const context: PluginContext = { options: normalized, pages, build: { changedOutputs, stats } };
  const plugins = [MarkdownPlugin, TemplatePlugin, ...(await loadConfiguredPlugins(normalized))];
  await runHook(plugins, 'onStart', context);
  await runHook(plugins, 'beforeBuild', context);
  const nextCache: BuildCache = { version: 1, templatesHash, pages: {} };
  const sourcePaths = await markdownFiles(normalized.contentDir!);
  for (const sourcePath of sourcePaths) {
    const relativePath = path.relative(normalized.contentDir!, sourcePath).split(path.sep).join('/');
    const source = await fs.readFile(sourcePath, 'utf8');
    const sourceHash = hash(source);
    const previous = cache?.pages[relativePath];
    const reusable = Boolean(previous && previous.sourceHash === sourceHash && previous.templateHash === templatesHash);
    const parsed = reusable && previous ? { data: previous.data, content: previous.content } : matter(source);
    const page: Page = {
      title: typeof parsed.data.title === 'string' && parsed.data.title.trim() ? parsed.data.title : path.basename(relativePath, path.extname(relativePath)),
      tags: [],
      html: parsed.content,
      sourcePath,
      outputPath: outputName(relativePath),
    };
    setParsedPageData(page, parsed.data as Frontmatter, parsed.content, reusable && previous ? previous.html : undefined);
    pages.push(page);
    const destination = path.join(normalized.outputDir!, page.outputPath);
    let outputExists = true;
    try { await fs.access(destination); } catch { outputExists = false; }
    if (!reusable || !outputExists) {
      changedOutputs.add(page.outputPath);
      stats.pagesBuilt += 1;
    } else {
      stats.pagesSkipped += 1;
      // Keep the stat deterministic; a skipped render represents at least one avoided millisecond.
      stats.timeSaved += 1;
    }
    if (!normalized.incremental) changedOutputs.add(page.outputPath);
    await runFileHook(plugins, page, context);
    nextCache.pages[relativePath] = {
      sourceHash,
      templateHash: templatesHash,
      data: parsed.data as Frontmatter,
      content: parsed.content,
      html: page.html,
      outputPath: page.outputPath,
    };
  }
  pages.sort((a, b) => (b.date ?? '').localeCompare(a.date ?? '') || a.outputPath.localeCompare(b.outputPath));
  if (!normalized.incremental || normalized.clean || !cache) await fs.rm(normalized.outputDir!, { recursive: true, force: true });
  await fs.mkdir(normalized.outputDir!, { recursive: true });
  await runHook(plugins, 'afterBuild', context);
  await runHook(plugins, 'onEnd', context);
  if (normalized.incremental) {
    for (const [oldSource, oldPage] of Object.entries(cache?.pages ?? {})) {
      if (!nextCache.pages[oldSource]) {
        await fs.rm(path.join(normalized.outputDir!, oldPage.outputPath), { force: true });
      }
    }
    await fs.mkdir(path.dirname(cacheFile), { recursive: true });
    await fs.writeFile(cacheFile, JSON.stringify(nextCache, null, 2));
  }
  return Object.assign(pages, { stats });
}
