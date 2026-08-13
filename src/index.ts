import path from 'node:path';
import { performance } from 'node:perf_hooks';
import { prepareCache, writeCache } from './cache';
import { loadPlugins } from './config';
import { MarkdownPlugin } from './plugins/markdown';
import { TemplatePlugin } from './plugins/template';
import { BuildContext, BuildOptions, BuildResult, Plugin } from './types';

async function runHook(
  plugins: Plugin[],
  hook: 'onStart' | 'beforeBuild' | 'afterBuild' | 'onEnd',
  context: BuildContext
): Promise<void> {
  for (const plugin of plugins) await plugin[hook]?.(context);
}

export async function buildSite(options: BuildOptions = {}): Promise<BuildResult> {
  const started = performance.now();
  const context: BuildContext = {
    contentDir: path.resolve(options.contentDir ?? 'content'),
    outputDir: path.resolve(options.outputDir ?? 'dist'),
    templatesDir: path.resolve(options.templatesDir ?? 'templates'),
    pages: [],
    incremental: options.incremental === true || options.clean === true,
    pagesToBuild: new Set(),
    renderedHtml: new Map(),
    stats: { pagesBuilt: 0, pagesSkipped: 0, timeSavedMs: 0, durationMs: 0 }
  };
  const plugins: Plugin[] = [new MarkdownPlugin(), new TemplatePlugin(), ...loadPlugins(options)];
  let buildError: unknown;

  try {
    if (context.incremental) await prepareCache(context, options);
    await runHook(plugins, 'onStart', context);
    await runHook(plugins, 'beforeBuild', context);
    for (const page of context.pages) {
      if (context.incremental && !context.pagesToBuild.has(page.sourcePath)) continue;
      for (const plugin of plugins) await plugin.onFile?.(page, context);
    }
    await runHook(plugins, 'afterBuild', context);
    if (context.incremental) await writeCache(context);
    context.stats.durationMs = Math.max(0, performance.now() - started);
    const result = context.pages as BuildResult;
    Object.defineProperty(result, 'stats', { value: context.stats, enumerable: false });
    return result;
  } catch (error) {
    buildError = error;
    throw error;
  } finally {
    try {
      await runHook(plugins, 'onEnd', context);
    } catch (error) {
      if (buildError === undefined) throw error;
    }
  }
}

export { MarkdownPlugin } from './plugins/markdown';
export { TemplatePlugin } from './plugins/template';
export { DevServerPlugin } from './plugins/dev-server';
export type { BuildContext, BuildOptions, BuildResult, BuildStats, Page, Plugin, SsgConfig } from './types';
