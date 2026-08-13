import { createHash } from 'node:crypto';
import { existsSync } from 'node:fs';
import { mkdir, readdir, readFile, rm, writeFile } from 'node:fs/promises';
import { extname, resolve } from 'node:path';
import { MarkdownPlugin } from './plugins/markdown';
import { TemplatePlugin } from './plugins/template';
import type { Plugin, PluginContext, SsgConfig } from './plugin';

export interface Page {
  sourcePath: string;
  outputPath: string;
  title: string;
  date?: string;
  tags: string[];
  html: string;
}

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
  incremental?: boolean;
  clean?: boolean;
}

export interface CachedPage {
  sourceHash: string;
  templateHash: string;
  page: Page;
  data: PageData;
  renderedHtml?: string;
}

interface CacheManifest {
  version: 1;
  templateHash: string;
  pages: Record<string, CachedPage>;
}

export interface BuildStats {
  pagesBuilt: number;
  pagesSkipped: number;
  timeSaved: number;
}

export interface PageData {
  title?: unknown;
  date?: unknown;
  tags?: unknown;
  template?: unknown;
  layout?: unknown;
  [key: string]: unknown;
}

async function runHook(plugins: Plugin[], hook: Exclude<keyof Plugin, 'onFile'>, context: PluginContext): Promise<void> {
  for (const plugin of plugins) {
    const handler = plugin[hook];
    if (!handler) continue;
    await handler(context);
  }
}

async function runFileHook(plugins: Plugin[], page: Page, context: PluginContext): Promise<void> {
  for (const plugin of plugins) {
    if (plugin.onFile) await plugin.onFile(page, context);
  }
}

function configuredPlugins(): Plugin[] {
  const configPath = resolve('ssg.config.ts');
  if (!existsSync(configPath)) return [];
  // Register TypeScript support when the compiled CLI loads a TypeScript config.
  try { require('ts-node/register/transpile-only'); } catch { /* ts-node is already registered or unavailable. */ }
  const loaded = require(configPath) as SsgConfig | Plugin[] | { default?: SsgConfig | Plugin[] };
  const config = 'default' in loaded && loaded.default ? loaded.default : loaded;
  return Array.isArray(config) ? config : config.plugins ?? [];
}

export class SsgEngine {
  stats: BuildStats = { pagesBuilt: 0, pagesSkipped: 0, timeSaved: 0 };

  constructor(private readonly plugins: Plugin[] = [new MarkdownPlugin(), new TemplatePlugin()]) {}

  async build(options: BuildOptions = {}): Promise<Page[]> {
    const context: PluginContext = {
      options: {
        contentDir: resolve(options.contentDir ?? 'content'),
        outputDir: resolve(options.outputDir ?? 'dist'),
        templatesDir: resolve(options.templatesDir ?? 'templates'),
        incremental: options.incremental ?? false,
        clean: options.clean ?? false
      },
      pages: [],
      sourcePages: []
    };
    this.stats = { pagesBuilt: 0, pagesSkipped: 0, timeSaved: 0 };
    await runHook(this.plugins, 'onStart', context);
    const manifestPath = resolve(context.options.outputDir, '.ssg-cache.json');
    const previousCache = options.incremental && !options.clean ? await readManifest(manifestPath) : undefined;
    const incremental = Boolean(previousCache);
    const templateHash = await hashTemplates(context.options.templatesDir);
    if (!incremental) await rm(context.options.outputDir, { recursive: true, force: true });
    await mkdir(context.options.outputDir, { recursive: true });
    context.cache = {
      pages: previousCache?.pages ?? {},
      reusableSources: new Set(),
      templateHash
    };
    await runHook(this.plugins, 'beforeBuild', context);
    const currentSources = new Set(context.sourcePages.map(({ page }) => page.sourcePath));
    for (const sourcePath of Object.keys(context.cache.pages)) {
      if (!currentSources.has(sourcePath)) {
        await rm(resolve(context.options.outputDir, context.cache.pages[sourcePath].page.outputPath), { force: true });
        delete context.cache.pages[sourcePath];
      }
    }
    const changedPages = new Set<Page>();
    for (const { page, data } of context.sourcePages) {
      const cached = context.cache.pages[page.sourcePath];
      const sourceHash = hash(await readFile(page.sourcePath, 'utf8'));
      const destination = resolve(context.options.outputDir, page.outputPath);
      const reusable = incremental && cached?.sourceHash === sourceHash && cached.templateHash === templateHash && existsSync(destination);
      context.cache.pages[page.sourcePath] = { sourceHash, templateHash, page, data, renderedHtml: cached?.renderedHtml };
      if (reusable) {
        context.cache.reusableSources.add(page.sourcePath);
        this.stats.pagesSkipped += 1;
      } else {
        changedPages.add(page);
        this.stats.pagesBuilt += 1;
      }
    }
    for (const page of context.pages) if (changedPages.has(page)) await runFileHook(this.plugins, page, context);
    await runHook(this.plugins, 'afterBuild', context);
    await writeFile(manifestPath, JSON.stringify({ version: 1, templateHash, pages: context.cache.pages }, null, 2));
    this.stats.timeSaved = this.stats.pagesSkipped;
    await runHook(this.plugins, 'onEnd', context);
    return context.pages;
  }
}

function hash(value: string): string {
  return createHash('sha256').update(value).digest('hex');
}

async function readManifest(path: string): Promise<CacheManifest | undefined> {
  try {
    const cache = JSON.parse(await readFile(path, 'utf8')) as CacheManifest;
    return cache.version === 1 && cache.pages ? cache : undefined;
  } catch {
    return undefined;
  }
}

async function hashTemplates(directory: string): Promise<string> {
  async function files(path: string): Promise<string[]> {
    try {
      const entries = await readdir(path, { withFileTypes: true });
      const nested = await Promise.all(entries.map(async (entry) => {
        const entryPath = resolve(path, entry.name);
        if (entry.isDirectory()) return files(entryPath);
        return entry.isFile() && extname(entry.name) === '.hbs' ? [entryPath] : [];
      }));
      return nested.flat();
    } catch (error: unknown) {
      if (error instanceof Error && 'code' in error && error.code === 'ENOENT') return [];
      throw error;
    }
  }
  const paths = (await files(directory)).sort();
  return hash((await Promise.all(paths.map(async (path) => `${path}:${await readFile(path, 'utf8')}`))).join('\n'));
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  return new SsgEngine([new MarkdownPlugin(), new TemplatePlugin(), ...configuredPlugins()]).build(options);
}

export async function buildSiteWithStats(options: BuildOptions = {}): Promise<{ pages: Page[]; stats: BuildStats }> {
  const engine = new SsgEngine([new MarkdownPlugin(), new TemplatePlugin(), ...configuredPlugins()]);
  const pages = await engine.build(options);
  return { pages, stats: engine.stats };
}
