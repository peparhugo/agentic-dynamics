import { SSGEngine } from './engine';
import type { Page } from './types';

export type { Page } from './types';

export { FRONTMATTER_DELIMITERS, parseMarkdown, readPages, sortPages } from './markdown';
export {
  escapeHtml,
  pageContext,
  renderIndex,
  renderIndexWithTemplates,
  renderPage,
  renderPageWithTemplates,
} from './render';
export {
  DEFAULT_LAYOUT,
  DEFAULT_TEMPLATE,
  DEFAULT_TEMPLATES_DIR,
  detectEngine,
  loadTemplates,
  renderTemplateFile,
} from './templates';
export type { TemplateEngine, TemplateFile, TemplateSet } from './templates';

export { SSGEngine } from './engine';
export type { EngineOptions } from './engine';

export { PluginPipeline, PLUGIN_HOOKS } from './plugin';
export type { Plugin, PluginContext, PluginHook, SSGConfig } from './types';

export { MarkdownPlugin } from './plugins/markdown';
export { TemplatePlugin } from './plugins/template';
export { DevServerPlugin } from './plugins/dev-server';

export {
  DEFAULT_CONFIG_FILE,
  DEFAULT_PLUGINS_DIR,
  ensureTypeScriptLoader,
  loadConfig,
  loadPlugin,
  loadPluginsFromConfig,
  loadTsModule,
  normalizeConfig,
  resolveConfigPath,
  toPlugin,
} from './plugin-loader';

import { DEFAULT_TEMPLATES_DIR } from './templates';

export const DEFAULT_CONTENT_DIR = './content';
export const DEFAULT_OUTPUT_DIR = './dist';

/**
 * Generate the whole site: the engine reads Markdown from `contentDir`, runs
 * the built-in plugin pipeline (markdown, templates, live-reload helpers) plus
 * any plugins registered in `ssg.config.ts`, and writes one HTML file per page
 * into `outputDir` plus an `index.html`. Returns the pages.
 */
export function build(
  contentDir: string = DEFAULT_CONTENT_DIR,
  outputDir: string = DEFAULT_OUTPUT_DIR,
  templatesDir: string = DEFAULT_TEMPLATES_DIR
): Page[] {
  return new SSGEngine({ contentDir, outputDir, templatesDir }).build();
}
