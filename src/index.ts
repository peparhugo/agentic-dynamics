import { promises as fs } from 'node:fs';
import { createHash } from 'node:crypto';
import path from 'node:path';
import { loadPlugins } from './config';
import { MarkdownPlugin } from './plugins/markdown';
import { TemplatePlugin } from './plugins/template';
import {
  BuildContext,
  BuildOptions,
  BuildStats,
  GeneratedPage,
  Page,
  Plugin,
  ResolvedBuildOptions,
} from './plugin';

const CACHE_VERSION = 1;

interface CachedPage {
  sourceHash: string;
  templateHash: string;
  buildTimeMs: number;
  page: Page;
}

interface CacheManifest {
  version: number;
  pages: Record<string, CachedPage>;
}

function hash(contents: string): string {
  return createHash('sha256').update(contents).digest('hex');
}

async function directoryHash(directory: string): Promise<string> {
  async function entries(current: string): Promise<Array<[string, string]>> {
    let children;
    try {
      children = await fs.readdir(current, { withFileTypes: true });
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === 'ENOENT') return [];
      throw error;
    }
    const nested = await Promise.all(children.map(async (child): Promise<Array<[string, string]>> => {
      const filePath = path.join(current, child.name);
      if (child.isDirectory()) return entries(filePath);
      if (!child.isFile()) return [];
      return [[path.relative(directory, filePath).split(path.sep).join('/'), await fs.readFile(filePath, 'utf8')]];
    }));
    return nested.flat();
  }

  const files = (await entries(directory)).sort(([left], [right]) => left.localeCompare(right));
  return hash(JSON.stringify(files));
}

async function readManifest(cachePath: string): Promise<CacheManifest | undefined> {
  try {
    const parsed = JSON.parse(await fs.readFile(cachePath, 'utf8')) as CacheManifest;
    if (parsed.version !== CACHE_VERSION || !parsed.pages || typeof parsed.pages !== 'object') return undefined;
    const valid = Object.values(parsed.pages).every((entry) => entry
      && typeof entry.sourceHash === 'string'
      && typeof entry.templateHash === 'string'
      && typeof entry.buildTimeMs === 'number'
      && entry.page
      && typeof entry.page.html === 'string'
      && typeof entry.page.title === 'string'
      && Array.isArray(entry.page.tags));
    if (!valid) return undefined;
    return parsed;
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT' || error instanceof SyntaxError) return undefined;
    throw error;
  }
}

async function fileExists(filePath: string): Promise<boolean> {
  try {
    return (await fs.stat(filePath)).isFile();
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return false;
    throw error;
  }
}

async function markdownFiles(directory: string): Promise<string[]> {
  let entries;
  try {
    entries = await fs.readdir(directory, { withFileTypes: true });
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') throw new Error(`Content directory does not exist: ${directory}`);
    throw error;
  }
  const files = await Promise.all(entries.map(async (entry) => {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) return markdownFiles(entryPath);
    return entry.isFile() && /\.md$/i.test(entry.name) ? [entryPath] : [];
  }));
  return files.flat().sort();
}

async function runHook<K extends 'onStart' | 'beforeBuild' | 'afterBuild' | 'onEnd'>(
  plugins: Plugin[],
  hook: K,
  context: BuildContext,
): Promise<void> {
  for (const plugin of plugins) await plugin[hook]?.(context);
}

export class SsgEngine {
  readonly options: ResolvedBuildOptions;
  readonly plugins: Plugin[];
  lastBuildStats: BuildStats = { pagesBuilt: 0, pagesSkipped: 0, durationMs: 0, timeSavedMs: 0 };

  constructor(options: ResolvedBuildOptions, plugins: Plugin[]) {
    this.options = options;
    this.plugins = plugins;
  }

  async build(): Promise<GeneratedPage[]> {
    const startedAt = process.hrtime.bigint();
    const stats: BuildStats = { pagesBuilt: 0, pagesSkipped: 0, durationMs: 0, timeSavedMs: 0 };
    const context: BuildContext = { options: this.options, pages: [], stats };
    const cachePath = path.join(this.options.outputDir, '.ssg-cache.json');
    try {
      await runHook(this.plugins, 'onStart', context);
      await runHook(this.plugins, 'beforeBuild', context);
      const files = await markdownFiles(this.options.contentDir);
      const previousManifest = this.options.incremental && !this.options.clean
        ? await readManifest(cachePath)
        : undefined;
      const cleanBuild = !this.options.incremental || this.options.clean || !previousManifest;
      if (cleanBuild) await fs.rm(this.options.outputDir, { recursive: true, force: true });
      await fs.mkdir(this.options.outputDir, { recursive: true });
      const templateHash = await directoryHash(this.options.templatesDir);
      const nextManifest: CacheManifest = { version: CACHE_VERSION, pages: {} };

      for (const sourcePath of files) {
        const relativePath = path.relative(this.options.contentDir, sourcePath);
        const outputRelativePath = relativePath.replace(/\.md$/i, '.html');
        const outputPath = path.join(this.options.outputDir, outputRelativePath);
        const source = await fs.readFile(sourcePath, 'utf8');
        const sourceHash = hash(source);
        const cached = previousManifest?.pages[relativePath];
        if (!cleanBuild && cached?.sourceHash === sourceHash && cached.templateHash === templateHash
          && await fileExists(outputPath)) {
          const page = { ...cached.page, sourcePath, outputPath, source };
          context.pages.push(page);
          nextManifest.pages[relativePath] = { ...cached, page };
          stats.pagesSkipped += 1;
          stats.timeSavedMs += cached.buildTimeMs;
          continue;
        }

        const pageStartedAt = process.hrtime.bigint();
        const page: Page = {
          sourcePath,
          outputPath,
          url: outputRelativePath.split(path.sep).join('/'),
          source,
          content: '',
          data: {},
          title: path.basename(sourcePath, path.extname(sourcePath)),
          tags: [],
          body: '',
          html: '',
        };
        for (const plugin of this.plugins) await plugin.onFile?.(page, context);
        await fs.mkdir(path.dirname(page.outputPath), { recursive: true });
        await fs.writeFile(page.outputPath, page.html, 'utf8');
        context.pages.push(page);
        const buildTimeMs = Number(process.hrtime.bigint() - pageStartedAt) / 1_000_000;
        nextManifest.pages[relativePath] = { sourceHash, templateHash, buildTimeMs, page };
        stats.pagesBuilt += 1;
      }
      if (!cleanBuild && previousManifest) {
        await Promise.all(Object.keys(previousManifest.pages)
          .filter((relativePath) => !nextManifest.pages[relativePath])
          .map((relativePath) => fs.rm(path.join(
            this.options.outputDir,
            relativePath.replace(/\.md$/i, '.html'),
          ), { force: true })));
      }
      context.pages.sort((left, right) => left.title.localeCompare(right.title));
      await runHook(this.plugins, 'afterBuild', context);
      if (this.options.incremental) await fs.writeFile(cachePath, JSON.stringify(nextManifest, null, 2), 'utf8');
      return context.pages.map(({ title, date, tags, sourcePath, outputPath, url }) => ({
        title, date, tags, sourcePath, outputPath, url,
      }));
    } finally {
      stats.durationMs = Number(process.hrtime.bigint() - startedAt) / 1_000_000;
      this.lastBuildStats = stats;
      await runHook(this.plugins, 'onEnd', context);
    }
  }
}

export async function createEngine(options: BuildOptions = {}): Promise<SsgEngine> {
  const configFile = path.resolve(options.configFile ?? './ssg.config.ts');
  const resolved: ResolvedBuildOptions = {
    contentDir: path.resolve(options.contentDir ?? './content'),
    outputDir: path.resolve(options.outputDir ?? './dist'),
    templatesDir: path.resolve(options.templatesDir ?? './templates'),
    configFile,
    incremental: options.incremental ?? false,
    clean: options.clean ?? false,
  };
  const configured = options.plugins ?? await loadPlugins(configFile);
  return new SsgEngine(resolved, [new MarkdownPlugin(), new TemplatePlugin(), ...configured]);
}

export async function buildSite(options: BuildOptions = {}): Promise<GeneratedPage[]> {
  return (await createEngine(options)).build();
}

export * from './plugin';
export { MarkdownPlugin } from './plugins/markdown';
export { TemplatePlugin } from './plugins/template';
export { DevServerPlugin } from './plugins/dev-server';
export { DevServer, ServeOptions, startDevServer } from './server';
