import * as path from 'path';
import { BuildOptions, BuildResult, Page, Plugin } from './plugin';
import { Engine } from './engine';
import { MarkdownPlugin } from './plugins/markdown';
import { TemplatePlugin } from './plugins/templates';

export { Page, BuildOptions, BuildResult, BuildStats } from './plugin';
export { escapeHtml } from './render';

export function build(options: BuildOptions): BuildResult {
  const templatesDir = options.templatesDir ?? path.resolve('templates');
  const plugins: Plugin[] = [new MarkdownPlugin(), new TemplatePlugin(templatesDir)];
  if (options.plugins) {
    plugins.push(...options.plugins);
  }

  const engine = new Engine(
    {
      contentDir: options.contentDir,
      outputDir: options.outputDir,
      templatesDir,
      incremental: options.incremental,
      clean: options.clean,
      cacheFile: options.cacheFile,
    },
    plugins
  );

  return engine.build();
}
