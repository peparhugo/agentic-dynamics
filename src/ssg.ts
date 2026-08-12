import { basename, extname, join, relative } from 'path';
import { existsSync, readFileSync, rmSync } from 'fs';
import { Page } from './page';
import { Plugin, PluginContext } from './plugin';
import { loadPlugins } from './config';
import { MarkdownPlugin } from './plugins/markdown';
import { TemplatePlugin } from './plugins/template';
import { listMarkdownFiles } from './files';
import {
  BuildStats,
  CachedPageData,
  IncrementalCache,
  computeTemplateHash,
  hashFile,
  toPosixPath,
} from './cache';

export interface SsgOptions {
  contentDir: string;
  outputDir: string;
  templatesDir: string;
  plugins?: Plugin[];
}

export interface IncrementalBuildOptions {
  clean?: boolean;
}

export interface BuildResult {
  pages: Page[];
  stats: BuildStats;
}

function defaultPlugins(): Plugin[] {
  return [new MarkdownPlugin(), new TemplatePlugin()];
}

function buildPipeline(extra: Plugin[] | undefined): Plugin[] {
  const pipeline = defaultPlugins()
    .concat(loadPlugins())
    .concat(extra ?? []);
  const names = new Set<string>();
  const unique: Plugin[] = [];
  for (const plugin of pipeline) {
    if (names.has(plugin.name)) continue;
    names.add(plugin.name);
    unique.push(plugin);
  }
  return unique;
}

export function createEngine(options: SsgOptions): SsgEngine {
  return new SsgEngine(options);
}

export class SsgEngine {
  private readonly plugins: Plugin[];
  private readonly context: PluginContext;

  constructor(options: SsgOptions) {
    this.context = {
      contentDir: options.contentDir,
      outputDir: options.outputDir,
      templatesDir: options.templatesDir,
    };
    this.plugins = buildPipeline(options.plugins);
  }

  get pipeline(): Plugin[] {
    return this.plugins;
  }

  start(): void {
    for (const plugin of this.plugins) {
      plugin.onStart?.(this.context);
    }
  }

  build(): Page[] {
    for (const plugin of this.plugins) {
      plugin.beforeBuild?.(this.context);
    }

    const files = listMarkdownFiles(this.context.contentDir);
    const pages: Page[] = [];
    for (const file of files) {
      pages.push(this.runPipelineOnFile(file));
    }
    pages.sort((a, b) => b.date.localeCompare(a.date));

    for (const plugin of this.plugins) {
      plugin.afterBuild?.(this.context, pages);
    }
    for (const plugin of this.plugins) {
      plugin.onEnd?.(this.context);
    }

    return pages;
  }

  buildIncremental(options: IncrementalBuildOptions = {}): BuildResult {
    for (const plugin of this.plugins) {
      plugin.beforeBuild?.(this.context);
    }

    const files = listMarkdownFiles(this.context.contentDir);
    const cache = IncrementalCache.load(this.context.outputDir, options.clean ?? false);
    const templateHash = computeTemplateHash(this.context.templatesDir);
    const templateChanged = cache.templateHash !== templateHash;
    cache.setTemplateHash(templateHash);

    const pages: Page[] = [];
    let pagesBuilt = 0;
    let pagesSkipped = 0;
    let timeSavedMs = 0;

    for (const file of files) {
      const relPath = toPosixPath(relative(this.context.contentDir, file));
      const sourceHash = hashFile(file);
      const cached = cache.get(relPath);

      if (cached && cached.sourceHash === sourceHash && !templateChanged && cached.html.length > 0) {
        pages.push(this.pageFromCache(file, cached));
        pagesSkipped += 1;
        timeSavedMs += cached.buildTimeMs;
        continue;
      }

      const startTime = process.hrtime.bigint();
      const page = this.runPipelineOnFile(file);
      const buildTimeMs = Math.max(1, Number(process.hrtime.bigint() - startTime) / 1_000_000);
      pages.push(page);
      pagesBuilt += 1;
      cache.set(relPath, {
        sourceHash,
        frontmatter: {
          title: page.title,
          date: page.date,
          tags: page.tags,
          template: page.template,
          layout: page.layout,
        },
        contentHtml: page.contentHtml,
        html: '',
        buildTimeMs,
      });
    }
    pages.sort((a, b) => b.date.localeCompare(a.date));

    for (const plugin of this.plugins) {
      plugin.afterBuild?.(this.context, pages);
    }
    for (const plugin of this.plugins) {
      plugin.onEnd?.(this.context);
    }

    this.syncCache(cache, files, pages);

    return { pages, stats: { pagesBuilt, pagesSkipped, timeSavedMs } };
  }

  private runPipelineOnFile(file: string): Page {
    let page: Page = {
      slug: basename(file, extname(file)),
      title: '',
      date: '',
      tags: [],
      contentHtml: '',
      filePath: file,
    };
    for (const plugin of this.plugins) {
      const result = plugin.onFile?.(page, this.context);
      if (result) page = result;
    }
    return page;
  }

  private pageFromCache(filePath: string, cached: CachedPageData): Page {
    const frontmatter = cached.frontmatter;
    const slug = basename(filePath, extname(filePath));
    return {
      slug,
      title: frontmatter.title ?? slug,
      date: frontmatter.date ?? '',
      tags: frontmatter.tags ?? [],
      contentHtml: cached.contentHtml,
      template: frontmatter.template,
      layout: frontmatter.layout,
      filePath,
      html: cached.html,
      cachedOutput: true,
    };
  }

  private syncCache(cache: IncrementalCache, files: string[], pages: Page[]): void {
    const current = new Set(files.map((file) => toPosixPath(relative(this.context.contentDir, file))));

    for (const relPath of Object.keys(cache.pages)) {
      if (current.has(relPath)) continue;
      const staleOutput = join(this.context.outputDir, `${basename(relPath, extname(relPath))}.html`);
      if (existsSync(staleOutput)) rmSync(staleOutput, { force: true });
      cache.delete(relPath);
    }

    for (const page of pages) {
      if (!page.filePath) continue;
      const relPath = toPosixPath(relative(this.context.contentDir, page.filePath));
      const cached = cache.get(relPath);
      if (!cached) continue;
      const outputPath = join(this.context.outputDir, `${page.slug}.html`);
      if (existsSync(outputPath)) {
        cached.html = readFileSync(outputPath, 'utf8');
        cache.set(relPath, cached);
      }
    }

    cache.save();
  }
}
