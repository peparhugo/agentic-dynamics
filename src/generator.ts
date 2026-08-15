import { SsgEngine } from './engine';
import { MarkdownPlugin } from './plugins/markdown-plugin';
import { TemplatePlugin } from './plugins/template-plugin';
import type { Plugin, PluginFactory, SSGConfig } from './plugins/types';
import { renderPage, renderIndex } from './render';
import { escapeHtml } from './escape';
import type { BuildStats } from './cache';
import type { Page } from './types';

export { escapeHtml, renderPage, renderIndex };
export type { BuildStats } from './cache';

export interface BuildOptions {
  contentDir: string;
  outputDir: string;
  templateDir?: string;
  defaultTemplate?: string;
  defaultLayout?: string;
  config?: SSGConfig;
  /** Only rebuild pages whose source or template inputs changed. */
  incremental?: boolean;
  /** Ignore the build cache and rebuild every page. */
  clean?: boolean;
  /** Location of the build cache manifest (default: `<outputDir>/.ssg-cache.json`). */
  cacheFile?: string;
}

export interface BuildResult {
  pages: Page[];
  stats: BuildStats;
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
export function buildSiteWithResult(
  options: BuildOptions,
  extraPlugins: Array<Plugin | PluginFactory> = []
): BuildResult {
  const engine = new SsgEngine(
    {
      contentDir: options.contentDir,
      outputDir: options.outputDir,
      templateDir: options.templateDir,
      defaultTemplate: options.defaultTemplate,
      defaultLayout: options.defaultLayout,
      config: options.config,
      command: 'build',
      incremental: options.incremental,
      clean: options.clean,
      cacheFile: options.cacheFile,
    },
    [new MarkdownPlugin(), new TemplatePlugin(), ...extraPlugins]
  );
  const pages = engine.runSync();
  return { pages, stats: engine.stats };
}

export function buildSite(
  options: BuildOptions,
  extraPlugins: Array<Plugin | PluginFactory> = []
): Page[] {
  return buildSiteWithResult(options, extraPlugins).pages;
}
