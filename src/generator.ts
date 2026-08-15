import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import { BuildOptions, Page, Plugin, PluginContext, resolveBuildOptions } from './plugin';
import MarkdownPlugin from './plugins/markdown';
import TemplatePlugin from './plugins/template';

export type { BuildOptions, Page, Plugin, PluginContext } from './plugin';

export interface BuildStats {
  pagesBuilt: number;
  pagesSkipped: number;
  timeSaved: number;
}

interface CachePage {
  url: string;
  sourceHash: string;
  templateHash: string;
  data: Page['data'];
  content: string;
  html: string;
  body: string;
  rendered?: string;
  output: string;
  durationMs: number;
}

interface BuildCache {
  version: 1;
  templateHash: string;
  pages: Record<string, CachePage>;
}

async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files: string[] = [];
  for (const entry of entries) {
    const file = path.join(directory, entry.name);
    if (entry.isDirectory()) files.push(...await markdownFiles(file));
    else if (/\.md$/i.test(entry.name)) files.push(file);
  }
  return files.sort();
}

async function templateFiles(directory: string): Promise<string[]> {
  try {
    const entries = await fs.readdir(directory, { withFileTypes: true });
    const files: string[] = [];
    for (const entry of entries) {
      const file = path.join(directory, entry.name);
      if (entry.isDirectory()) files.push(...await templateFiles(file));
      else if (/\.(?:hbs|ejs)$/i.test(entry.name)) files.push(file);
    }
    return files.sort();
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return [];
    throw error;
  }
}

async function hashFile(file: string): Promise<string> {
  return crypto.createHash('sha256').update(await fs.readFile(file)).digest('hex');
}

async function hashTemplates(directory: string, defaultTemplate: string): Promise<string> {
  const files = await templateFiles(directory);
  const hash = crypto.createHash('sha256').update(defaultTemplate);
  for (const file of files) hash.update(path.relative(directory, file)).update(await hashFile(file));
  return hash.digest('hex');
}

async function readCache(file: string): Promise<BuildCache | undefined> {
  try {
    const cache = JSON.parse(await fs.readFile(file, 'utf8')) as BuildCache;
    return cache.version === 1 && cache.pages && typeof cache.templateHash === 'string' ? cache : undefined;
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT' || error instanceof SyntaxError) return undefined;
    throw error;
  }
}

function configuredPlugins(config: unknown): Plugin[] {
  if (!config || typeof config !== 'object') return [];
  const value = Array.isArray(config) ? config : (config as { plugins?: unknown }).plugins;
  if (!Array.isArray(value)) return [];
  return value.flatMap((plugin) => {
    if (typeof plugin === 'function') return [new (plugin as new () => Plugin)()];
    if (plugin && typeof plugin === 'object') return [plugin as Plugin];
    return [];
  });
}

function loadConfig(filename: string): Plugin[] {
  try {
    // require is intentional: it works with ts-jest and with compiled JS configs.
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const loaded = require(filename) as { default?: unknown } & Record<string, unknown>;
    return configuredPlugins(loaded.default ?? loaded);
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'MODULE_NOT_FOUND') return [];
    throw error;
  }
}

export class SSG {
  private readonly options: PluginContext['options'];
  private readonly plugins: Plugin[];
  private readonly incremental: boolean;
  private readonly clean: boolean;
  private running = false;

  constructor(options: BuildOptions = {}, additionalPlugins: Plugin[] = []) {
    this.options = resolveBuildOptions(options);
    this.incremental = Boolean(options.incremental);
    this.clean = Boolean(options.clean);
    const configFile = path.resolve(options.configFile ?? './ssg.config.ts');
    const configured = options.plugins ?? loadConfig(configFile);
    // External onFile hooks run between parsing and rendering so they can modify pages.
    this.plugins = [new MarkdownPlugin(), ...configured, ...additionalPlugins, new TemplatePlugin()];
  }

  async build(): Promise<BuildStats> {
    if (this.running) return { pagesBuilt: 0, pagesSkipped: 0, timeSaved: 0 };
    this.running = true;
    const stats: BuildStats = { pagesBuilt: 0, pagesSkipped: 0, timeSaved: 0 };
    const cacheFile = path.join(this.options.outputDir, '.ssg-cache.json');
    const oldCache = this.incremental && !this.clean ? await readCache(cacheFile) : undefined;
    const files = await markdownFiles(this.options.contentDir);
    const templateHash = await hashTemplates(this.options.templatesDir, this.options.defaultTemplate);
    const cacheUsable = Boolean(oldCache && oldCache.templateHash === templateHash);
    const nextCache: BuildCache = { version: 1, templateHash, pages: {} };
    const pages: Page[] = files.map((source) => ({
      source,
      url: path.relative(this.options.contentDir, source).replace(/\.md$/i, '.html').split(path.sep).join('/'),
      data: {}, content: '', html: '', body: '',
    }));
    const context: PluginContext = {
      options: this.options, pages, files, state: new Map(), rebuild: async () => { await this.build(); },
    };
    try {
      if (!cacheUsable) await fs.rm(this.options.outputDir, { recursive: true, force: true });
      await fs.mkdir(this.options.outputDir, { recursive: true });
      if (cacheUsable && oldCache) {
        const currentSources = new Set(files.map((file) => path.relative(this.options.contentDir, file)));
        await Promise.all(Object.entries(oldCache.pages)
          .filter(([source]) => !currentSources.has(source))
          .map(([, page]) => fs.rm(path.join(this.options.outputDir, page.url), { force: true })));
      }
      await this.runHook('onStart', context);
      await this.runHook('beforeBuild', context);
      for (const page of pages) {
        const relativeSource = path.relative(this.options.contentDir, page.source);
        const previous = cacheUsable ? oldCache?.pages[relativeSource] : undefined;
        const sourceHash = await hashFile(page.source);
        const destination = path.join(this.options.outputDir, page.url);
        if (previous?.sourceHash === sourceHash && previous.templateHash === templateHash && previous.output) {
          page.data = previous.data;
          page.content = previous.content;
          page.html = previous.html;
          page.body = previous.body;
          page.rendered = previous.rendered;
          await fs.mkdir(path.dirname(destination), { recursive: true });
          await fs.writeFile(destination, previous.output, 'utf8');
          nextCache.pages[relativeSource] = previous;
          stats.pagesSkipped += 1;
          stats.timeSaved += previous.durationMs;
          continue;
        }
        const pageStarted = Date.now();
        await this.runFileHooks(page, context);
        const output = await fs.readFile(destination, 'utf8');
        nextCache.pages[relativeSource] = {
          url: page.url, sourceHash, templateHash, data: page.data, content: page.content, html: page.html,
          body: page.body, rendered: page.rendered, output, durationMs: Date.now() - pageStarted,
        };
        stats.pagesBuilt += 1;
      }
      await this.runHook('afterBuild', context);
      await this.runHook('onEnd', context);
      await fs.writeFile(cacheFile, JSON.stringify(nextCache, null, 2), 'utf8');
      return stats;
    } finally {
      this.running = false;
    }
  }

  private async runHook(hook: 'onStart' | 'beforeBuild' | 'afterBuild' | 'onEnd', context: PluginContext): Promise<void> {
    for (const plugin of this.plugins) if (plugin[hook]) await plugin[hook]!(context);
  }

  private async runFileHooks(page: Page, context: PluginContext): Promise<void> {
    for (const plugin of this.plugins) if (plugin.onFile) await plugin.onFile(page, context);
  }
}

export async function buildSite(options: BuildOptions = {}): Promise<BuildStats> {
  return new SSG(options).build();
}
