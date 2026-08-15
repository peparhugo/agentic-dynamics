import { promises as fs, type Dirent } from 'node:fs';
import { createHash } from 'node:crypto';
import path from 'node:path';
import { loadConfiguredPlugins } from './config';
import { MarkdownPlugin } from './plugins/markdown';
import { TemplatePlugin } from './plugins/template';
import type { BuildContext, BuildOptions, BuildStats, GeneratedPage, Plugin } from './types';

const CACHE_VERSION = 1;

interface CacheEntry {
  sourceHash: string;
  buildTime: number;
  page: GeneratedPage;
}

interface CacheManifest {
  version: number;
  templateHash: string;
  pages: Record<string, CacheEntry>;
}

async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files = await Promise.all(entries.map(async (entry) => {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) return markdownFiles(entryPath);
    return entry.isFile() && /\.md$/i.test(entry.name) ? [entryPath] : [];
  }));
  return files.flat().sort();
}

async function directoryHash(directory: string): Promise<string> {
  const hash = createHash('sha256');
  async function visit(current: string): Promise<void> {
    let entries: Dirent[];
    try { entries = await fs.readdir(current, { withFileTypes: true }); } catch (error) {
      if ((error as NodeJS.ErrnoException).code === 'ENOENT') return;
      throw error;
    }
    for (const entry of entries.sort((a, b) => a.name.localeCompare(b.name))) {
      const entryPath = path.join(current, entry.name);
      if (entry.isDirectory()) await visit(entryPath);
      else if (entry.isFile()) {
        hash.update(path.relative(directory, entryPath));
        hash.update(await fs.readFile(entryPath));
      }
    }
  }
  await visit(directory);
  return hash.digest('hex');
}

async function fileHash(filePath: string): Promise<string> {
  return createHash('sha256').update(await fs.readFile(filePath)).digest('hex');
}

async function readManifest(filePath: string): Promise<CacheManifest | undefined> {
  try {
    const value = JSON.parse(await fs.readFile(filePath, 'utf8')) as Partial<CacheManifest> | null;
    if (value?.version === CACHE_VERSION && typeof value.templateHash === 'string'
        && value.pages && typeof value.pages === 'object') return value as CacheManifest;
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== 'ENOENT' && !(error instanceof SyntaxError)) throw error;
  }
  return undefined;
}

async function exists(filePath: string): Promise<boolean> {
  try { await fs.access(filePath); return true; } catch { return false; }
}

export class SSGEngine {
  readonly plugins: Plugin[];
  readonly context: BuildContext;
  stats: BuildStats = { pagesBuilt: 0, pagesSkipped: 0, timeSaved: 0, duration: 0 };
  private readonly options: BuildOptions;

  constructor(options: BuildOptions = {}) {
    const resolved = {
      contentDir: path.resolve(options.contentDir ?? './content'),
      outputDir: path.resolve(options.outputDir ?? './dist'),
      templatesDir: path.resolve(options.templatesDir ?? './templates'),
    };
    this.options = options;
    this.context = {
      options: resolved,
      pages: [],
      incremental: {
        enabled: Boolean(options.incremental), cleanBuild: true, changedSources: new Set(), skippedSources: new Set(),
      },
    };
    this.plugins = [new MarkdownPlugin(), new TemplatePlugin(), ...loadConfiguredPlugins(options)];
  }

  private async runHook(hook: 'onStart' | 'beforeBuild' | 'afterBuild' | 'onEnd'): Promise<void> {
    for (const plugin of this.plugins) await plugin[hook]?.(this.context);
  }

  async build(): Promise<GeneratedPage[]> {
    const startedAt = Date.now();
    try {
      await this.runHook('onStart');
      const files = await markdownFiles(this.context.options.contentDir);
      const cachePath = path.join(this.context.options.outputDir, '.ssg-cache.json');
      const manifest = this.options.incremental && !this.options.clean ? await readManifest(cachePath) : undefined;
      const templateHash = await directoryHash(this.context.options.templatesDir);
      const cleanBuild = !this.options.incremental || Boolean(this.options.clean) || !manifest;
      const changedSources = new Set<string>();
      const skippedSources = new Set<string>();
      const sourceHashes = new Map(await Promise.all(files.map(async (file): Promise<[string, string]> => [file, await fileHash(file)])));
      const pages = await Promise.all(files.map(async (sourcePath): Promise<GeneratedPage> => {
        const relative = path.relative(this.context.options.contentDir, sourcePath).replace(/\.md$/i, '.html');
        const cacheKey = path.relative(this.context.options.contentDir, sourcePath).split(path.sep).join('/');
        const cached = manifest?.pages[cacheKey];
        const outputPath = path.join(this.context.options.outputDir, relative);
        if (!cleanBuild && manifest?.templateHash === templateHash && cached && cached.sourceHash === sourceHashes.get(sourcePath)
            && await exists(outputPath)) {
          skippedSources.add(sourcePath);
          return { ...cached.page, sourcePath, outputPath, url: relative.split(path.sep).map(encodeURIComponent).join('/') };
        }
        changedSources.add(sourcePath);
        return {
          sourcePath,
          outputPath,
          url: relative.split(path.sep).map(encodeURIComponent).join('/'),
          title: path.basename(sourcePath, path.extname(sourcePath)),
          data: {},
          content: '',
          html: '',
        };
      }));
      Object.assign(this.context.incremental, { cleanBuild, changedSources, skippedSources });
      this.context.pages.splice(0, this.context.pages.length, ...pages);

      if (!cleanBuild && manifest) {
        const currentKeys = new Set(files.map((file) => path.relative(this.context.options.contentDir, file).split(path.sep).join('/')));
        await Promise.all(Object.keys(manifest.pages).filter((key) => !currentKeys.has(key)).map((key) => {
          const relative = key.replace(/\.md$/i, '.html').split('/').join(path.sep);
          return fs.rm(path.join(this.context.options.outputDir, relative), { force: true });
        }));
      }

      await this.runHook('beforeBuild');
      for (const page of this.context.pages) {
        if (skippedSources.has(page.sourcePath)) continue;
        for (const plugin of this.plugins) await plugin.onFile?.(page, this.context);
      }
      this.context.pages.sort((a, b) => {
        if (a.data.date && b.data.date) return b.data.date.localeCompare(a.data.date);
        return a.title.localeCompare(b.title);
      });
      await this.runHook('afterBuild');

      const duration = Date.now() - startedAt;
      const previousTime = [...skippedSources].reduce((total, sourcePath) => {
        const key = path.relative(this.context.options.contentDir, sourcePath).split(path.sep).join('/');
        return total + (manifest?.pages[key]?.buildTime ?? 0);
      }, 0);
      this.stats = {
        pagesBuilt: changedSources.size,
        pagesSkipped: skippedSources.size,
        timeSaved: Math.round(previousTime),
        duration,
      };
      const buildTime = changedSources.size ? duration / changedSources.size : 0;
      const cachePages: Record<string, CacheEntry> = {};
      for (const page of this.context.pages) {
        const key = path.relative(this.context.options.contentDir, page.sourcePath).split(path.sep).join('/');
        cachePages[key] = {
          sourceHash: sourceHashes.get(page.sourcePath)!,
          buildTime: changedSources.has(page.sourcePath) ? buildTime : (manifest?.pages[key]?.buildTime ?? 0),
          page,
        };
      }
      await fs.writeFile(cachePath, `${JSON.stringify({ version: CACHE_VERSION, templateHash, pages: cachePages }, null, 2)}\n`, 'utf8');
      return this.context.pages;
    } finally {
      await this.runHook('onEnd');
    }
  }
}

export async function buildSite(options: BuildOptions = {}): Promise<GeneratedPage[]> {
  return new SSGEngine(options).build();
}
