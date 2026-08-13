import { promises as fs } from 'node:fs';
import { createHash } from 'node:crypto';
import path from 'node:path';
import type { BuildContext, BuildOptions, BuildPage, BuildStats, Page, Plugin } from './plugin.js';

const CACHE_VERSION = 1;

interface CacheEntry {
  sourceHash: string;
  templateHash: string;
  buildTimeMs: number;
  page: BuildPage;
}

interface CacheManifest {
  version: number;
  pages: Record<string, CacheEntry>;
}

async function markdownFiles(directory: string, base = directory): Promise<string[]> {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files = await Promise.all(entries.map(async (entry) => {
    const absolutePath = path.join(directory, entry.name);
    if (entry.isDirectory()) return markdownFiles(absolutePath, base);
    return entry.isFile() && /\.md$/i.test(entry.name) ? [path.relative(base, absolutePath)] : [];
  }));
  return files.flat().sort((left, right) => left.localeCompare(right));
}

async function filesWithExtension(directory: string, extension: RegExp, base = directory): Promise<string[]> {
  let entries;
  try {
    entries = await fs.readdir(directory, { withFileTypes: true });
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return [];
    throw error;
  }
  const files = await Promise.all(entries.map(async (entry) => {
    const absolutePath = path.join(directory, entry.name);
    if (entry.isDirectory()) return filesWithExtension(absolutePath, extension, base);
    return entry.isFile() && extension.test(entry.name) ? [path.relative(base, absolutePath)] : [];
  }));
  return files.flat().sort((left, right) => left.localeCompare(right));
}

function hash(value: string): string {
  return createHash('sha256').update(value).digest('hex');
}

async function templatesHash(directory: string): Promise<string> {
  const files = await filesWithExtension(directory, /\.hbs$/i);
  const contents = await Promise.all(files.map(async (file) => `${file}\0${await fs.readFile(path.join(directory, file), 'utf8')}\0`));
  return hash(contents.join(''));
}

async function readManifest(filePath: string): Promise<CacheManifest | undefined> {
  try {
    const manifest: unknown = JSON.parse(await fs.readFile(filePath, 'utf8'));
    if (!manifest || typeof manifest !== 'object') return undefined;
    const candidate = manifest as Partial<CacheManifest>;
    return candidate.version === CACHE_VERSION && candidate.pages && typeof candidate.pages === 'object'
      ? candidate as CacheManifest : undefined;
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT' || error instanceof SyntaxError) return undefined;
    throw error;
  }
}

function outputPathFor(relativePath: string): string {
  const parsed = path.parse(relativePath);
  return path.join(parsed.dir, `${parsed.name}.html`);
}

export class SsgEngine {
  private started = false;
  private buildCount = 0;
  private pages: BuildPage[] = [];
  private stats: BuildStats = { pagesBuilt: 0, pagesSkipped: 0, durationMs: 0, timeSavedMs: 0 };
  readonly options: BuildContext['options'];
  private readonly incremental: boolean;
  private readonly clean: boolean;

  constructor(options: BuildOptions, private readonly plugins: Plugin[]) {
    this.options = {
      contentDir: path.resolve(options.contentDir ?? 'content'),
      outputDir: path.resolve(options.outputDir ?? 'dist'),
      templatesDir: path.resolve(options.templatesDir ?? 'templates')
    };
    this.incremental = options.incremental ?? false;
    this.clean = options.clean ?? false;
  }

  private context(): BuildContext {
    return { options: this.options, pages: this.pages, initialBuild: this.buildCount === 0 };
  }

  async start(): Promise<void> {
    if (this.started) return;
    this.started = true;
    for (const plugin of this.plugins) await plugin.onStart?.(this.context());
  }

  async build(): Promise<Page[]> {
    const buildStarted = performance.now();
    await this.start();
    this.pages = [];
    const context = this.context();
    for (const plugin of this.plugins) await plugin.beforeBuild?.(context);
    const files = await markdownFiles(this.options.contentDir);
    const sources = await Promise.all(files.map(async (sourcePath) => ({
      sourcePath,
      source: await fs.readFile(path.join(this.options.contentDir, sourcePath), 'utf8')
    })));
    const templateHash = await templatesHash(this.options.templatesDir);
    const cacheFile = path.join(this.options.outputDir, '.ssg-cache.json');
    const previous = this.incremental && !this.clean ? await readManifest(cacheFile) : undefined;
    const canIncrement = previous !== undefined;
    this.pages.push(...sources.map(({ sourcePath, source }): BuildPage => {
      const outputPath = outputPathFor(sourcePath);
      return {
        title: path.parse(sourcePath).name,
        tags: [],
        sourcePath,
        outputPath,
        url: `/${outputPath.split(path.sep).join('/')}`,
        source,
        html: '',
        data: {}
      };
    }));
    const destinations = new Set<string>();
    for (const page of this.pages) {
      if (page.outputPath === 'index.html' || destinations.has(page.outputPath)) {
        throw new Error(`Output path collision: ${page.outputPath}`);
      }
      destinations.add(page.outputPath);
    }
    if (!this.incremental || !canIncrement || this.clean) {
      await fs.rm(this.options.outputDir, { recursive: true, force: true });
    } else {
      const currentOutputs = new Set(this.pages.map((page) => page.outputPath));
      await Promise.all(Object.values(previous.pages)
        .filter(({ page }) => !currentOutputs.has(page.outputPath))
        .map(({ page }) => fs.rm(path.join(this.options.outputDir, page.outputPath), { force: true })));
    }
    await fs.mkdir(this.options.outputDir, { recursive: true });
    const nextManifest: CacheManifest = { version: CACHE_VERSION, pages: {} };
    let pagesBuilt = 0;
    let pagesSkipped = 0;
    let timeSavedMs = 0;
    for (let index = 0; index < this.pages.length; index += 1) {
      let page = this.pages[index];
      const sourceHash = hash(page.source);
      const cached = previous?.pages[page.sourcePath];
      const destinationExists = await fs.stat(path.join(this.options.outputDir, page.outputPath))
        .then((stat) => stat.isFile(), (error: NodeJS.ErrnoException) => error.code === 'ENOENT' ? false : Promise.reject(error));
      if (canIncrement && cached?.sourceHash === sourceHash && cached.templateHash === templateHash && destinationExists) {
        page = { ...cached.page, source: page.source, data: { ...cached.page.data } };
        this.pages[index] = page;
        pagesSkipped += 1;
        timeSavedMs += cached.buildTimeMs;
        nextManifest.pages[page.sourcePath] = cached;
        continue;
      }
      const pageStarted = performance.now();
      for (const plugin of this.plugins) await plugin.onFile?.(page, context);
      const buildTimeMs = Math.max(1, Math.round(performance.now() - pageStarted));
      pagesBuilt += 1;
      nextManifest.pages[page.sourcePath] = { sourceHash, templateHash, buildTimeMs, page };
    }
    for (const plugin of this.plugins) await plugin.afterBuild?.(context);
    if (this.incremental) await fs.writeFile(cacheFile, `${JSON.stringify(nextManifest, null, 2)}\n`, 'utf8');
    this.buildCount += 1;
    this.stats = {
      pagesBuilt,
      pagesSkipped,
      durationMs: Math.round(performance.now() - buildStarted),
      timeSavedMs
    };
    return this.pages.map(({ source: _source, html: _html, data: _data, template: _template, layout: _layout, ...page }) => page);
  }

  getBuildStats(): BuildStats {
    return { ...this.stats };
  }

  async end(): Promise<void> {
    if (!this.started) return;
    const context = this.context();
    for (const plugin of this.plugins) await plugin.onEnd?.(context);
    this.started = false;
  }
}
