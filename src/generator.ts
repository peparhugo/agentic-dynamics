import { SSGEngine } from './engine';
import { createMarkdownPlugin } from './plugins/markdownPlugin';
import { createTemplatePlugin } from './plugins/templatePlugin';
import { BuildOptions, BuildResult } from './types';

export { findMarkdownFiles, loadPages } from './markdownLoader';

/**
 * Builds the site using the built-in Markdown + Template plugins, run
 * synchronously through SSGEngine. For a custom plugin pipeline (including
 * async plugins like DevServerPlugin), construct an `SSGEngine` directly
 * and call `run()`.
 */
export function buildSite(options: BuildOptions): BuildResult {
  const engine = new SSGEngine([createMarkdownPlugin(), createTemplatePlugin()]);
  return engine.runSync(options);
}
