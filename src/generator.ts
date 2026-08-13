import { createHash } from 'node:crypto';
import { readFile, readdir, stat, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { loadPlugins } from './config.js';
import { MarkdownPlugin } from './plugins/markdown.js';
import { TemplatePlugin } from './plugins/template.js';
import type { BuildContext, BuildOptions, BuildStats, Plugin } from './plugin.js';

export interface Page {
  slug: string;
  title: string;
  date?: string;
  tags: string[];
  html: string;
  template?: string;
  layout?: string;
  data: Record<string, unknown>;
  sourcePath?: string;
  sourceHash?: string;
}

export type { BuildOptions, BuildContext, BuildStats, Plugin } from './plugin.js';

export class SsgEngine {
  public lastBuildStats: BuildStats = { pagesBuilt: 0, pagesSkipped: 0, timeSavedMs: 0 };
  constructor(private readonly options: BuildOptions = {}, private readonly plugins: Plugin[] = []) {}

  async build(): Promise<Page[]> {
    const context = this.context();
    try {
      await this.loadCache(context);
      await this.run('onStart', context);
      await this.run('beforeBuild', context);
      await this.selectPagesToBuild(context);
      for (const page of context.buildPages) {
        const startedAt = performance.now();
        await this.run('onFile', context, page);
        if (page.sourceHash) context.cache[page.slug] = { hash: page.sourceHash, renderTimeMs: performance.now() - startedAt };
      }
      await this.run('afterBuild', context);
      await this.writeCache(context);
      this.lastBuildStats = context.stats;
      return context.pages;
    } finally {
      await this.run('onEnd', context);
    }
  }

  private context(): BuildContext {
    return {
      options: {
        contentDir: path.resolve(this.options.contentDir ?? 'content'),
        outputDir: path.resolve(this.options.outputDir ?? 'dist'),
        templatesDir: path.resolve(this.options.templatesDir ?? 'templates'),
        incremental: this.options.incremental ?? false,
        clean: this.options.clean ?? false
      },
      pages: [],
      buildPages: [],
      cleanBuild: true,
      cacheFile: path.join(path.dirname(path.resolve(this.options.outputDir ?? 'dist')), '.ssg-cache.json'),
      previousCache: {},
      cache: {},
      stats: { pagesBuilt: 0, pagesSkipped: 0, timeSavedMs: 0 }
    };
  }

  private async loadCache(context: BuildContext): Promise<void> {
    if (!context.options.incremental || context.options.clean) return;
    try {
      const parsed = JSON.parse(await readFile(context.cacheFile, 'utf8')) as { pages?: Record<string, { hash: string; renderTimeMs: number }> };
      context.previousCache = parsed.pages ?? {};
      context.cleanBuild = false;
    } catch (error: unknown) {
      if ((error as NodeJS.ErrnoException).code !== 'ENOENT' && error instanceof SyntaxError === false) throw error;
    }
  }

  private async selectPagesToBuild(context: BuildContext): Promise<void> {
    const templateHash = await this.templateHash(context.options.templatesDir);
    for (const page of context.pages) {
      if (page.sourceHash) page.sourceHash = createHash('sha256').update(page.sourceHash).update(templateHash).digest('hex');
      const cached = page.sourceHash ? context.previousCache[page.slug] : undefined;
      const outputFile = path.join(context.options.outputDir, `${page.slug}.html`);
      if (!context.cleanBuild && cached?.hash === page.sourceHash && await this.fileExists(outputFile)) {
        context.cache[page.slug] = cached;
        context.stats.pagesSkipped += 1;
        context.stats.timeSavedMs += cached.renderTimeMs;
      } else {
        context.buildPages.push(page);
      }
    }
    context.stats.pagesBuilt = context.buildPages.length;
  }

  private async templateHash(templatesDir: string): Promise<string> {
    const hash = createHash('sha256');
    const visit = async (directory: string): Promise<void> => {
      let entries;
      try { entries = await readdir(directory, { withFileTypes: true }); } catch (error: unknown) {
        if ((error as NodeJS.ErrnoException).code === 'ENOENT') return;
        throw error;
      }
      for (const entry of entries.sort((left, right) => left.name.localeCompare(right.name))) {
        const entryPath = path.join(directory, entry.name);
        if (entry.isDirectory()) await visit(entryPath);
        else if (entry.isFile()) hash.update(path.relative(templatesDir, entryPath)).update(await readFile(entryPath));
      }
    };
    await visit(templatesDir);
    return hash.digest('hex');
  }

  private async fileExists(file: string): Promise<boolean> {
    try { return (await stat(file)).isFile(); } catch (error: unknown) {
      if ((error as NodeJS.ErrnoException).code === 'ENOENT') return false;
      throw error;
    }
  }

  private async writeCache(context: BuildContext): Promise<void> {
    if (!context.options.incremental) return;
    await writeFile(context.cacheFile, `${JSON.stringify({ version: 1, pages: context.cache }, null, 2)}\n`);
  }

  private async run(hook: keyof Plugin, context: BuildContext, page?: Page): Promise<void> {
    for (const plugin of this.plugins) {
      const handler = plugin[hook];
      if (!handler) continue;
      if (hook === 'onFile') await (handler as NonNullable<Plugin['onFile']>)(page!, context);
      else await (handler as (context: BuildContext) => void | Promise<void>)(context);
    }
  }
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  return (await buildSiteWithStats(options)).pages;
}

export async function buildSiteWithStats(options: BuildOptions = {}): Promise<{ pages: Page[]; stats: BuildStats }> {
  const configuredPlugins = await loadPlugins();
  const engine = new SsgEngine(options, [new MarkdownPlugin(), new TemplatePlugin(), ...configuredPlugins]);
  const pages = await engine.build();
  return { pages, stats: engine.lastBuildStats };
}

export async function readPages(contentDir: string): Promise<Page[]> {
  const context: BuildContext = { options: { contentDir: path.resolve(contentDir), outputDir: '', templatesDir: '', incremental: false, clean: false }, pages: [], buildPages: [], cleanBuild: true, cacheFile: '', previousCache: {}, cache: {}, stats: { pagesBuilt: 0, pagesSkipped: 0, timeSavedMs: 0 } };
  await new MarkdownPlugin().beforeBuild(context);
  return context.pages;
}
