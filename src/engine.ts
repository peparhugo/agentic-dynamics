import fs from 'fs';
import path from 'path';
import { runFileHooks, runHook, Plugin, PluginContext } from './plugin';
import { loadPlugins } from './config';
import { BuildCache, computeTemplateHash, CACHE_FILENAME, hashFile } from './cache';
import type { BuildOptions, BuildResult, BuildStats, Page } from './types';

const DEFAULT_TEMPLATES_DIR = './templates';

/**
 * The core SSG engine. It loads plugins, then orchestrates the plugin pipeline:
 *
 *   onStart -> beforeBuild -> onFile (per page) -> afterBuild -> onEnd
 *
 * The built-in MarkdownPlugin populates the page list during `beforeBuild` and
 * the built-in TemplatePlugin renders each page during `onFile`, so the engine
 * itself only concerns itself with wiring hooks together and writing files.
 *
 * With `incremental` enabled, the engine tracks file hashes in a
 * `.ssg-cache.json` manifest. Pages whose source and template hashes are
 * unchanged are restored from the cache and skip the `onFile` render phase.
 */
export function build(options: BuildOptions): BuildResult {
  const plugins: Plugin[] = loadPlugins(options);
  const incremental = options.incremental === true;

  const cacheFile = options.cacheFile ?? path.join(options.outputDir, CACHE_FILENAME);
  const cache = new BuildCache(cacheFile);

  if (incremental && options.clean === true) {
    cache.delete();
  }

  const useCache = incremental;
  let templateHash: string | undefined;
  if (useCache) {
    cache.load();
    templateHash = computeTemplateHash(options.templatesDir ?? DEFAULT_TEMPLATES_DIR);
  }

  const context: PluginContext = {
    options,
    pages: [],
    outputDir: options.outputDir,
    cache: useCache ? cache : undefined,
    templateHash: useCache ? templateHash : undefined,
  };

  runHook(plugins, 'onStart', context);
  runHook(plugins, 'beforeBuild', context);

  fs.mkdirSync(context.outputDir, { recursive: true });

  // Snapshot the parsed pages before per-page hooks mutate them, so the return
  // value mirrors the raw (Markdown) pages rather than the rendered output.
  const resultPages: Page[] = context.pages.map((page) => ({ ...page }));

  const stats: BuildStats = { pagesBuilt: 0, pagesSkipped: 0, timeSavedMs: 0 };

  for (const page of context.pages) {
    if (useCache && page.fresh) {
      const cached = cache.getPage(page.slug);
      if (cached) {
        page.html = cached.html;
        stats.pagesSkipped++;
        stats.timeSavedMs += cached.durationMs;
        continue;
      }
    }

    const bodyHtml = page.html;
    const started = Date.now();
    runFileHooks(plugins, page, context);
    const durationMs = Date.now() - started;
    stats.pagesBuilt++;

    if (useCache) {
      cache.setPage({
        slug: page.slug,
        sourcePath: page.sourcePath,
        sourceHash: page.sourceHash ?? hashFile(page.sourcePath),
        templateHash: templateHash ?? '',
        title: page.title,
        date: page.date,
        tags: page.tags,
        template: page.template,
        layout: page.layout,
        data: page.data,
        bodyHtml,
        html: page.html,
        durationMs,
      });
    }
  }

  for (const page of context.pages) {
    fs.writeFileSync(path.join(context.outputDir, `${page.slug}.html`), page.html);
  }

  runHook(plugins, 'afterBuild', context);
  runHook(plugins, 'onEnd', context);

  if (useCache) {
    cache.prune(context.pages.map((page) => page.slug));
    cache.save();
  }

  return { pages: resultPages, outputDir: context.outputDir, stats };
}
