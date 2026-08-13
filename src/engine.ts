import { createHash } from 'node:crypto';
import { promises as fs } from 'node:fs';
import path from 'node:path';
import type { Plugin, PluginContext } from './plugin';
import type { BuildOptions, BuildStats, Page } from './types';

export const pageSources = new WeakMap<Page, string>();

interface CacheEntry {
  sourceHash: string;
  templateHash: string;
  page: Page;
  buildTimeMs: number;
}

interface CacheManifest {
  version: 1;
  pages: Record<string, CacheEntry>;
}

const CACHE_FILE = '.ssg-cache.json';

function hash(parts: string[]): string {
  const digest = createHash('sha256');
  for (const part of parts) digest.update(part).update('\0');
  return digest.digest('hex');
}

async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files = await Promise.all(entries.map(async (entry) => {
    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) return markdownFiles(fullPath);
    return /\.md$/i.test(entry.name) ? [fullPath] : [];
  }));
  return files.flat().sort();
}

async function filesWithExtension(directory: string, extension: RegExp): Promise<string[]> {
  let entries;
  try {
    entries = await fs.readdir(directory, { withFileTypes: true });
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return [];
    throw error;
  }
  const files = await Promise.all(entries.map(async (entry) => {
    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) return filesWithExtension(fullPath, extension);
    return extension.test(entry.name) ? [fullPath] : [];
  }));
  return files.flat().sort();
}

async function templatesHash(directory: string): Promise<string> {
  const files = await filesWithExtension(directory, /\.hbs$/i);
  const parts: string[] = [];
  for (const file of files) {
    parts.push(path.relative(directory, file).split(path.sep).join('/'), await fs.readFile(file, 'utf8'));
  }
  return hash(parts);
}

async function loadManifest(file: string): Promise<CacheManifest | undefined> {
  try {
    const parsed = JSON.parse(await fs.readFile(file, 'utf8')) as Partial<CacheManifest>;
    if (parsed.version !== 1 || !parsed.pages || typeof parsed.pages !== 'object' || Array.isArray(parsed.pages)) {
      return undefined;
    }
    const valid = Object.values(parsed.pages).every((entry) => {
      if (!entry || typeof entry !== 'object') return false;
      const candidate = entry as Partial<CacheEntry>;
      return typeof candidate.sourceHash === 'string'
        && typeof candidate.templateHash === 'string'
        && typeof candidate.buildTimeMs === 'number'
        && !!candidate.page
        && typeof candidate.page.url === 'string';
    });
    if (!valid) return undefined;
    return parsed as CacheManifest;
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT' || error instanceof SyntaxError) return undefined;
    throw error;
  }
}

export class SSGEngine {
  readonly options: PluginContext['options'];
  readonly pages: Page[] = [];
  readonly stats: BuildStats = { pagesBuilt: 0, pagesSkipped: 0, durationMs: 0, timeSavedMs: 0 };
  private started = false;
  private ended = false;
  private readonly startedPlugins: Plugin[] = [];
  private readonly context: PluginContext;

  constructor(options: BuildOptions, readonly plugins: Plugin[]) {
    this.options = {
      ...options,
      content: path.resolve(options.content ?? './content'),
      output: path.resolve(options.output ?? './dist'),
      templates: path.resolve(options.templates ?? './templates'),
    };
    if (this.options.content === this.options.output) {
      throw new Error('Content and output directories must be different');
    }
    this.context = { options: this.options, pages: this.pages, stats: this.stats, build: () => this.build() };
  }

  async start(): Promise<void> {
    if (this.started) return;
    this.started = true;
    for (const plugin of this.plugins) {
      await plugin.onStart?.(this.context);
      this.startedPlugins.push(plugin);
    }
  }

  async build(): Promise<Page[]> {
    const buildStarted = performance.now();
    if (!this.started) await this.start();
    if (this.ended) throw new Error('Cannot build after the SSG engine has ended');
    const files = await markdownFiles(this.options.content);
    const cachePath = path.join(this.options.output, CACHE_FILE);
    const previous = this.options.incremental && !this.options.clean
      ? await loadManifest(cachePath)
      : undefined;
    const templateHash = await templatesHash(this.options.templates);
    const sourceDetails = await Promise.all(files.map(async (file) => {
      const relativePath = path.relative(this.options.content, file);
      const source = await fs.readFile(file, 'utf8');
      return { file, relativePath, source, sourceHash: hash([source]) };
    }));

    const nextManifest: CacheManifest = { version: 1, pages: {} };
    const pagesToBuild = new Set<Page>();
    const pageDetails = new WeakMap<Page, typeof sourceDetails[number]>();
    this.stats.pagesBuilt = 0;
    this.stats.pagesSkipped = 0;
    this.stats.durationMs = 0;
    this.stats.timeSavedMs = 0;

    this.pages.splice(0, this.pages.length, ...await Promise.all(sourceDetails.map(async (details) => {
      const cacheKey = details.relativePath.split(path.sep).join('/');
      const cached = previous?.pages[cacheKey];
      const cachedOutput = cached && path.join(this.options.output, ...cached.page.url.split('/'));
      if (cached && cached.sourceHash === details.sourceHash && cached.templateHash === templateHash
        && cachedOutput && await fs.stat(cachedOutput).then((stat) => stat.isFile()).catch(() => false)) {
        const page = structuredClone(cached.page);
        nextManifest.pages[cacheKey] = cached;
        this.stats.pagesSkipped += 1;
        this.stats.timeSavedMs += cached.buildTimeMs;
        return page;
      }
      const page: Page = {
        title: path.basename(details.file, path.extname(details.file)),
        tags: [],
        url: details.relativePath.replace(/\.md$/i, '.html').split(path.sep).join('/'),
        html: '',
      };
      pageSources.set(page, details.source);
      pageDetails.set(page, details);
      pagesToBuild.add(page);
      return page;
    })));

    if (!previous) await fs.rm(this.options.output, { recursive: true, force: true });
    await fs.mkdir(this.options.output, { recursive: true });
    if (previous) {
      const currentSources = new Set(sourceDetails.map(({ relativePath }) => relativePath.split(path.sep).join('/')));
      await Promise.all(Object.entries(previous.pages).map(async ([source, entry]) => {
        if (!currentSources.has(source)) {
          await fs.rm(path.join(this.options.output, ...entry.page.url.split('/')), { force: true });
        }
      }));
    }
    for (const plugin of this.plugins) await plugin.beforeBuild?.(this.context);
    for (const page of this.pages) {
      if (pagesToBuild.has(page)) {
        const pageStarted = performance.now();
        for (const plugin of this.plugins) await plugin.onFile?.(page, this.context);
        const source = pageDetails.get(page);
        if (source) {
          const cacheKey = source.relativePath.split(path.sep).join('/');
          nextManifest.pages[cacheKey] = {
            sourceHash: source.sourceHash,
            templateHash,
            page: structuredClone(page),
            buildTimeMs: performance.now() - pageStarted,
          };
        }
        this.stats.pagesBuilt += 1;
      }
    }
    this.pages.sort((left, right) => {
      if (left.date && right.date && left.date !== right.date) return right.date.localeCompare(left.date);
      if (left.date !== right.date) return left.date ? -1 : 1;
      return left.title.localeCompare(right.title);
    });
    for (const plugin of this.plugins) await plugin.afterBuild?.(this.context);
    await fs.writeFile(cachePath, `${JSON.stringify(nextManifest, null, 2)}\n`, 'utf8');
    this.stats.durationMs = performance.now() - buildStarted;
    return this.pages;
  }

  async end(): Promise<void> {
    if (!this.started || this.ended) return;
    this.ended = true;
    for (const plugin of this.startedPlugins) await plugin.onEnd?.(this.context);
  }
}
