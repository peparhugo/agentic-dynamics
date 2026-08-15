import fs from 'fs';
import path from 'path';
import { runFileHooks, runHook, Plugin, PluginContext } from './plugin';
import { loadPlugins } from './config';
import type { BuildOptions, BuildResult, Page } from './types';

/**
 * The core SSG engine. It loads plugins, then orchestrates the plugin pipeline:
 *
 *   onStart -> beforeBuild -> onFile (per page) -> afterBuild -> onEnd
 *
 * The built-in MarkdownPlugin populates the page list during `beforeBuild` and
 * the built-in TemplatePlugin renders each page during `onFile`, so the engine
 * itself only concerns itself with wiring hooks together and writing files.
 */
export function build(options: BuildOptions): BuildResult {
  const plugins: Plugin[] = loadPlugins(options);
  const context: PluginContext = {
    options,
    pages: [],
    outputDir: options.outputDir,
  };

  runHook(plugins, 'onStart', context);
  runHook(plugins, 'beforeBuild', context);

  fs.mkdirSync(context.outputDir, { recursive: true });

  // Snapshot the parsed pages before per-page hooks mutate them, so the return
  // value mirrors the raw (Markdown) pages rather than the rendered output.
  const resultPages: Page[] = context.pages.map((page) => ({ ...page }));

  for (const page of context.pages) {
    runFileHooks(plugins, page, context);
  }

  for (const page of context.pages) {
    fs.writeFileSync(path.join(context.outputDir, `${page.slug}.html`), page.html);
  }

  runHook(plugins, 'afterBuild', context);
  runHook(plugins, 'onEnd', context);

  return { pages: resultPages, outputDir: context.outputDir };
}
