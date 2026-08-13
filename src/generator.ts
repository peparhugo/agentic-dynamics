import { existsSync } from 'node:fs';
import { readFile, rm, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { BuildCache, BuildOptions, createBuildContext, Page, Plugin, prepareOutput, runHook, writeIndex } from './plugin';
import { loadConfiguredPlugins } from './config';
import { MarkdownPlugin } from './plugins/markdown';
import { TemplatePlugin } from './plugins/template';

export { BuildOptions, Page } from './plugin';

export const builtInPlugins = (): Plugin[] => [new MarkdownPlugin(), new TemplatePlugin()];

async function loadCache(cachePath: string): Promise<BuildCache | undefined> {
  try {
    const cache = JSON.parse(await readFile(cachePath, 'utf8')) as BuildCache;
    return cache.version === 1 && typeof cache.pages === 'object' ? cache : undefined;
  } catch {
    return undefined;
  }
}

export interface BuildResult {
  pages: Page[];
  stats: { built: number; skipped: number; timeSavedMs: number };
}

export async function buildSiteWithStats(options: BuildOptions = {}): Promise<BuildResult> {
  const context = createBuildContext(options);
  const plugins = [...builtInPlugins(), ...loadConfiguredPlugins(), ...(options.plugins ?? [])];
  if (options.incremental && !options.clean) context.cache = await loadCache(context.cachePath);
  await runHook(plugins, 'onStart', context);
  await prepareOutput(context);
  await runHook(plugins, 'beforeBuild', context);
  const cacheUsable = options.incremental && !options.clean && context.cache?.templateHash === context.templateHash;
  const currentPaths = new Set(context.pages.map((page) => page.outputPath));
  if (options.incremental && !options.clean && context.cache) {
    await Promise.all(Object.keys(context.cache.pages)
      .filter((outputPath) => !currentPaths.has(outputPath))
      .map((outputPath) => rm(join(context.outputDir, outputPath), { force: true })));
  }
  for (const page of context.pages) {
    const cached = context.cache?.pages[page.outputPath];
    const destination = join(context.outputDir, page.outputPath);
    if (cacheUsable && cached?.sourceHash === page.sourceHash && existsSync(destination)) {
      context.skippedPages.add(page.outputPath);
      context.stats.skipped += 1;
      context.stats.timeSavedMs += cached.renderTimeMs ?? 0;
      continue;
    }
    const startedAt = performance.now();
    await runHook(plugins, 'onFile', context, page);
    page.renderTimeMs = Math.round(performance.now() - startedAt);
    context.stats.built += 1;
  }
  await writeIndex(context);
  const cache: BuildCache = {
    version: 1,
    templateHash: context.templateHash,
    pages: Object.fromEntries(context.pages.map((page) => [page.outputPath, {
      sourceHash: page.sourceHash ?? '',
      page: { ...page, sourceHash: undefined, renderTimeMs: undefined },
      renderTimeMs: page.renderTimeMs ?? 0,
    }])),
  };
  await writeFile(context.cachePath, JSON.stringify(cache, null, 2));
  await runHook(plugins, 'afterBuild', context);
  await runHook(plugins, 'onEnd', context);
  return { pages: context.pages, stats: context.stats };
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  return (await buildSiteWithStats(options)).pages;
}
