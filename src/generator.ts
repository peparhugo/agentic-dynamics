import { SsgEngine } from './engine';
import { MarkdownPlugin } from './plugins/markdown-plugin';
import { TemplatePlugin } from './plugins/template-plugin';
import type { Plugin, PluginFactory, SSGConfig } from './plugins/types';
import { renderPage, renderIndex } from './render';
import { escapeHtml } from './escape';
import type { Page } from './types';

export { escapeHtml, renderPage, renderIndex };

export interface BuildOptions {
  contentDir: string;
  outputDir: string;
  templateDir?: string;
  defaultTemplate?: string;
  defaultLayout?: string;
  config?: SSGConfig;
}

/**
 * Build the site: every markdown file in `contentDir` becomes a page in
 * `outputDir` and an `index.html` listing all pages is generated.
 * When a template directory exists (default `./templates`), pages are rendered
 * through its Handlebars templates, layouts and partials.
 * Returns the list of generated pages.
 *
 * The build runs through the core SSG engine with the built-in markdown and
 * template plugins; additional plugins can be supplied for custom processing.
 */
export function buildSite(
  options: BuildOptions,
  extraPlugins: Array<Plugin | PluginFactory> = []
): Page[] {
  const engine = new SsgEngine(
    {
      contentDir: options.contentDir,
      outputDir: options.outputDir,
      templateDir: options.templateDir,
      defaultTemplate: options.defaultTemplate,
      defaultLayout: options.defaultLayout,
      config: options.config,
      command: 'build',
    },
    [new MarkdownPlugin(), new TemplatePlugin(), ...extraPlugins]
  );
  return engine.runSync();
}
