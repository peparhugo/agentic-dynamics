import { promises as fs } from 'node:fs';
import { createHash } from 'node:crypto';
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
  incremental?: boolean;
  clean?: boolean;
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

export interface BuildStats {
  pagesBuilt: number;
  pagesSkipped: number;
  timeSavedMs: number;
  durationMs: number;
  incremental: boolean;
}

export type BuildPages = Page[] & { stats: BuildStats };

interface CacheEntry {
  sourceHash: string;
  templateHash: string;
  html: string;
  page: Page;
  frontmatter?: Record<string, unknown>;
}

interface CacheManifest {
  version: 1;
  entries: Record<string, CacheEntry>;
}

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

async function filesIn(directory: string): Promise<string[]> {
  try {
    const entries = await fs.readdir(directory, { withFileTypes: true });
    const files: string[] = [];
    for (const entry of entries) {
      const file = path.join(directory, entry.name);
      if (entry.isDirectory()) files.push(...await filesIn(file));
      else if (entry.isFile()) files.push(file);
    }
    return files.sort((a, b) => a.localeCompare(b));
  } catch { return []; }
}

async function hashFiles(files: string[], root: string): Promise<string> {
  const hash = createHash('sha256');
  for (const file of files) {
    hash.update(path.relative(root, file));
    hash.update(await fs.readFile(file));
  }
  return hash.digest('hex');
}

async function readManifest(file: string): Promise<CacheManifest | undefined> {
  try {
    const manifest = JSON.parse(await fs.readFile(file, 'utf8')) as CacheManifest;
    return manifest.version === 1 && manifest.entries ? manifest : undefined;
  } catch { return undefined; }
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

export async function buildSite(options: SiteOptions = {}): Promise<BuildPages> {
  const started = Date.now();
  const contentDir = path.resolve(options.contentDir ?? './content');
  const outputDir = path.resolve(options.outputDir ?? './dist');
  const templatesDir = path.resolve(options.templatesDir ?? './templates');
  const cacheFile = path.join(outputDir, '.ssg-cache.json');
  const incremental = options.incremental === true;
  const previous = incremental && !options.clean ? await readManifest(cacheFile) : undefined;
  const templateHash = await hashFiles(await filesIn(templatesDir), templatesDir);
  const cache: CacheManifest = { version: 1, entries: {} };
  const plugins = [new MarkdownPlugin(), new TemplatePlugin(), ...configuredPlugins(options), ...(options.plugins ?? [])];
  const pages: Page[] = [];
  const context: PluginContext = { options, contentDir, outputDir, templatesDir, pages };

  await hooks(plugins, 'onStart', context);
  if (!previous) await fs.rm(outputDir, { recursive: true, force: true });
  await fs.mkdir(outputDir, { recursive: true });
  await hooks(plugins, 'beforeBuild', context);

  const sourceFiles = await markdownFiles(contentDir);
  const currentSources = new Set(sourceFiles.map((file) => path.relative(contentDir, file)));
  if (previous) {
    for (const [source, entry] of Object.entries(previous.entries)) {
      if (!currentSources.has(source)) await fs.rm(path.join(outputDir, entry.page.output), { force: true });
    }
  }
  for (const file of sourceFiles) {
    const relative = path.relative(contentDir, file);
    const sourceHash = createHash('sha256').update(await fs.readFile(file)).digest('hex');
    const cached = previous?.entries[relative];
    const cachedOutput = cached ? path.join(outputDir, cached.page.output) : '';
    let outputExists = false;
    if (cachedOutput) {
      try { outputExists = (await fs.stat(cachedOutput)).isFile(); } catch { outputExists = false; }
    }
    if (cached && outputExists && cached.sourceHash === sourceHash && cached.templateHash === templateHash) {
      const page = cached.page;
      Object.defineProperty(page, 'filePath', { value: file, enumerable: false, writable: true });
      pages.push(page);
      cache.entries[relative] = cached;
      continue;
    }
    let page: Page = { source: relative, output: relative.replace(/\.md$/i, '.html'), title: path.basename(relative, path.extname(relative)), tags: [], html: '' };
    Object.defineProperty(page, 'filePath', { value: file, enumerable: false, writable: true });
    for (const plugin of plugins) if (plugin.onFile) page = (await plugin.onFile(page, context)) ?? page;
    pages.push(page);
    const destination = path.join(outputDir, page.output);
    await fs.mkdir(path.dirname(destination), { recursive: true });
    await fs.writeFile(destination, page.html, 'utf8');
    cache.entries[relative] = {
      sourceHash, templateHash, html: page.html, page,
      frontmatter: (page as Page & { frontmatter?: Record<string, unknown> }).frontmatter,
    };
  }

  await hooks(plugins, 'afterBuild', context);
  await hooks(plugins, 'onEnd', context);
  await fs.writeFile(cacheFile, JSON.stringify(cache, null, 2), 'utf8');
  const pagesBuilt = Object.keys(cache.entries).filter((key) => !previous?.entries[key] || previous.entries[key].sourceHash !== cache.entries[key].sourceHash || previous.entries[key].templateHash !== cache.entries[key].templateHash).length;
  const pagesSkipped = pages.length - pagesBuilt;
  const durationMs = Date.now() - started;
  const result = pages as BuildPages;
  result.stats = { pagesBuilt, pagesSkipped, timeSavedMs: pagesSkipped ? Math.max(1, durationMs * pagesSkipped / Math.max(1, pagesBuilt + pagesSkipped)) : 0, durationMs, incremental };
  return result;
}

export { MarkdownPlugin } from './markdown-plugin';
export { TemplatePlugin } from './template-plugin';
export type { Plugin, PluginContext, PluginModule } from './plugin';
