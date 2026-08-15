import fs from 'fs';
import { PageData, BuildContext, PluginManager } from './plugin.js';
import { MarkdownPlugin } from './plugins/markdown-plugin.js';
import { TemplatePlugin } from './plugins/template-plugin.js';
import { CacheManager, BuildStats } from './cache.js';

export interface GeneratorOptions {
  contentDir: string;
  outputDir: string;
  templatesDir?: string;
  layoutsDir?: string;
  partialsDir?: string;
  incremental?: boolean;
  clean?: boolean;
}

export { PageData, BuildStats };

export async function generate(options: GeneratorOptions): Promise<BuildStats> {
  const { contentDir, outputDir, incremental = false, clean = false } = options;
  const templatesDir = options.templatesDir || './templates';
  const layoutsDir = options.layoutsDir || './templates/layouts';
  const partialsDir = options.partialsDir || './templates/partials';

  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  const cacheManager = new CacheManager(outputDir);

  if (clean) {
    cacheManager.clear();
  }

  const pluginManager = new PluginManager();
  pluginManager.addPlugin(new MarkdownPlugin());
  pluginManager.addPlugin(new TemplatePlugin());

  const context: BuildContext = {
    contentDir,
    outputDir,
    templatesDir,
    layoutsDir,
    partialsDir,
    pages: [],
    cacheManager,
    incremental,
    pagesBuilt: 0,
    pagesSkipped: 0
  };

  await pluginManager.callHook('onStart', context);
  await pluginManager.callHook('beforeBuild', context);

  for (const page of context.pages) {
    await pluginManager.callHook('onFile', context, page);
  }

  await pluginManager.callHook('afterBuild', context);
  await pluginManager.callHook('onEnd', context);

  cacheManager.save();

  const stats = cacheManager.getStats(context.pagesBuilt, context.pagesSkipped);

  console.log(
    `Generated site with ${context.pages.length} page(s) in ${outputDir} (${stats.pagesBuilt} built, ${stats.pagesSkipped} skipped)`
  );

  return stats;
}
