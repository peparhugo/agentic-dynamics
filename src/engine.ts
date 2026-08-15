import fs from 'fs';
import path from 'path';
import { BuildOptions, Page, BuildResult, BuildStats } from './types';
import { Plugin, PluginContext, PluginPipeline, createContext } from './plugin';
import { MarkdownPlugin } from './plugins/markdown';
import { TemplatePlugin } from './plugins/templates';
import { BuildCache, CACHE_FILENAME, computeTemplateHash } from './cache';
import { pageToFrontmatter } from './markdown';

export function createDefaultPlugins(userPlugins: Plugin[] = []): Plugin[] {
  return [new MarkdownPlugin(), ...userPlugins, new TemplatePlugin()];
}

export class SSGEngine {
  private readonly pipeline: PluginPipeline;

  constructor(plugins: Plugin[]) {
    this.pipeline = new PluginPipeline(plugins);
  }

  getPlugins(): Plugin[] {
    return this.pipeline.getPlugins();
  }

  build(options: BuildOptions): Page[] {
    return this.buildInternal(options).pages;
  }

  buildIncremental(options: BuildOptions): BuildResult {
    return this.buildInternal(options);
  }

  private buildInternal(options: BuildOptions): BuildResult {
    const incremental = options.incremental === true;
    const clean = options.clean === true;
    const cacheFile = options.cacheFile ?? path.join(options.outputDir, CACHE_FILENAME);
    const cache = new BuildCache(cacheFile);
    if (clean) cache.reset();

    const context = createContext(options);
    context.cache = cache;
    context.incremental = incremental;
    context.clean = clean;

    this.pipeline.runOnStart(context);
    this.pipeline.runBeforeBuild(context);

    fs.mkdirSync(context.outputDir, { recursive: true });

    const templatesDir = context.templatesDir;
    const stats: BuildStats = {
      pagesBuilt: 0,
      pagesSkipped: 0,
      totalPages: context.pages.length,
      timeSavedMs: 0,
    };

    let totalRenderMs = 0;
    const pages = context.pages;

    for (let i = 0; i < pages.length; i++) {
      const page = pages[i];
      const slug = page.slug;
      const sourceHash = page.sourceHash ?? '';
      const templateHash = computeTemplateHash(templatesDir, page);
      const outputFile = path.join(context.outputDir, `${slug}.html`);

      if (incremental && !clean) {
        const entry = cache.getEntry(slug);
        if (
          entry &&
          entry.sourceHash === sourceHash &&
          entry.templateHash === templateHash &&
          fs.existsSync(outputFile)
        ) {
          stats.pagesSkipped++;
          continue;
        }
      }

      const start = Date.now();
      const transformed = this.pipeline.runOnFile(page, context);
      if (transformed !== undefined) {
        pages[i] = transformed;
      }
      totalRenderMs += Date.now() - start;

      cache.setEntry({
        slug,
        sourceHash,
        templateHash,
        frontmatter: pageToFrontmatter(pages[i]),
        bodyHtml: pages[i].html,
      });

      stats.pagesBuilt++;
    }

    if (stats.pagesBuilt > 0) {
      stats.timeSavedMs = Math.round(stats.pagesSkipped * (totalRenderMs / stats.pagesBuilt));
    }

    this.pipeline.runAfterBuild(context);
    this.pipeline.runOnEnd(context);

    cache.save();

    return { pages: context.pages, stats };
  }

  async buildAsync(options: BuildOptions): Promise<Page[]> {
    const context = createContext(options);

    await this.pipeline.runOnStartAsync(context);
    await this.pipeline.runBeforeBuildAsync(context);

    await fs.promises.mkdir(context.outputDir, { recursive: true });

    const pages = context.pages;
    for (let i = 0; i < pages.length; i++) {
      const transformed = await this.pipeline.runOnFileAsync(pages[i], context);
      if (transformed !== undefined) {
        pages[i] = transformed;
      }
    }

    await this.pipeline.runAfterBuildAsync(context);
    await this.pipeline.runOnEndAsync(context);

    return context.pages;
  }
}

export function createEngine(userPlugins: Plugin[] = []): SSGEngine {
  return new SSGEngine(createDefaultPlugins(userPlugins));
}
