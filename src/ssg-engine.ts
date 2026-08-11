import fs from 'fs';
import path from 'path';
import { Plugin, BuildContext } from './plugin';
import { PageData } from './types';
import { CacheManager, BuildStats, CacheEntry } from './cache';

export { BuildStats } from './cache';
export { CacheManager } from './cache';

export class SsgEngine {
  plugins: Plugin[];

  constructor(plugins: Plugin[]) {
    this.plugins = plugins;
  }

  async build(options: {
    contentDir: string;
    outputDir: string;
    templatesDir: string;
    incremental?: boolean;
    clean?: boolean;
  }): Promise<BuildStats> {
    const stats: BuildStats = { pagesBuilt: 0, pagesSkipped: 0, timeSavedMs: 0 };

    const cache = new CacheManager(options.outputDir);

    if (options.clean) {
      cache.delete();
    }

    const isIncremental = !!(options.incremental);
    let templateHash = '';

    if (isIncremental) {
      cache.load();
      templateHash = CacheManager.computeTemplateHash(options.templatesDir);
    }

    const ctx: BuildContext = {
      contentDir: options.contentDir,
      outputDir: options.outputDir,
      templatesDir: options.templatesDir,
      pages: [],
      incremental: isIncremental,
      buildStats: stats,
    };

    await this.runHook('onStart', ctx);
    await this.runHook('beforeBuild', ctx);

    if (!fs.existsSync(ctx.contentDir)) {
      throw new Error(`Content directory not found: ${ctx.contentDir}`);
    }

    const files = fs.readdirSync(ctx.contentDir).filter((f) => f.endsWith('.md'));
    const cachedHtmlMap = new Map<string, string>();
    const builtSlugs: string[] = [];

    for (const file of files) {
      const slug = file.replace(/\.md$/, '');
      const filePath = path.join(ctx.contentDir, file);
      const rawContent = fs.readFileSync(filePath, 'utf-8');
      const contentHash = CacheManager.computeContentHash(filePath);

      if (isIncremental && !cache.isStale(slug, contentHash, templateHash)) {
        const cached = cache.getCachedPage(slug);
        if (cached) {
          const cachedPage: PageData = {
            slug,
            frontmatter: cached.frontmatter,
            content: rawContent,
            html: cached.html,
          };
          ctx.pages.push(cachedPage);
          cachedHtmlMap.set(slug, cached.html);
          stats.pagesSkipped++;
          const perPageTimeMs = 10;
          stats.timeSavedMs += perPageTimeMs;
          continue;
        }
      }

      let page: PageData = {
        slug,
        frontmatter: { title: slug, date: '', tags: [] },
        content: rawContent,
        html: '',
      };

      for (const plugin of this.plugins) {
        if (plugin.onFile) {
          const result = await plugin.onFile(page, ctx);
          if (result !== undefined) {
            page = result;
          }
        }
      }

      ctx.pages.push(page);
      stats.pagesBuilt++;
      builtSlugs.push(slug);

      if (isIncremental) {
        const entry: CacheEntry = {
          slug,
          contentHash,
          templateHash,
          html: page.html,
          frontmatter: page.frontmatter,
        };
        cache.setEntry(entry);
      }
    }

    if (cachedHtmlMap.size > 0) {
      ctx.cachedPages = cachedHtmlMap;
    }

    await this.runHook('afterBuild', ctx);

    if (isIncremental) {
      for (const slug of builtSlugs) {
        const htmlFile = path.join(options.outputDir, `${slug}.html`);
        if (fs.existsSync(htmlFile)) {
          const renderedHtml = fs.readFileSync(htmlFile, 'utf-8');
          const entry = cache.getEntry(slug);
          if (entry) {
            entry.html = renderedHtml;
            cache.setEntry(entry);
          }
        }
      }
      cache.save();
    }

    await this.runHook('onEnd', ctx);

    if (isIncremental && stats.pagesSkipped > 0) {
      console.log(
        `[ssg] Built ${stats.pagesBuilt} page(s), skipped ${stats.pagesSkipped} page(s) unchanged, saved ~${stats.timeSavedMs}ms`
      );
    }

    return stats;
  }

  private async runHook(
    hook: 'onStart' | 'beforeBuild' | 'afterBuild' | 'onEnd',
    ctx: BuildContext
  ): Promise<void> {
    for (const plugin of this.plugins) {
      const fn = plugin[hook];
      if (fn) {
        await fn.call(plugin, ctx);
      }
    }
  }
}
