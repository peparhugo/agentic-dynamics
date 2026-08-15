import fs from 'fs';
import { PageData, BuildContext, PluginManager } from './plugin.js';
import { MarkdownPlugin } from './plugins/markdown-plugin.js';
import { TemplatePlugin } from './plugins/template-plugin.js';

export interface GeneratorOptions {
  contentDir: string;
  outputDir: string;
  templatesDir?: string;
  layoutsDir?: string;
  partialsDir?: string;
}

export { PageData };

export async function generate(options: GeneratorOptions): Promise<void> {
  const { contentDir, outputDir } = options;
  const templatesDir = options.templatesDir || './templates';
  const layoutsDir = options.layoutsDir || './templates/layouts';
  const partialsDir = options.partialsDir || './templates/partials';

  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
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
    pages: []
  };

  await pluginManager.callHook('onStart', context);
  await pluginManager.callHook('beforeBuild', context);

  for (const page of context.pages) {
    await pluginManager.callHook('onFile', context, page);
  }

  await pluginManager.callHook('afterBuild', context);
  await pluginManager.callHook('onEnd', context);

  console.log(`Generated site with ${context.pages.length} page(s) in ${outputDir}`);
}
