import { loadConfig } from './config';
import { loadPlugins } from './loader';
import { SsgEngine } from './engine';
import { BuildOptions, Page } from './types';

/**
 * Build a static site from Markdown content.
 *
 * Delegates to the core SSG engine, which orchestrates the plugin pipeline
 * (markdown parsing, template rendering, and any configured plugins).
 */
export async function build(options: BuildOptions): Promise<Page[]> {
  const config = await loadConfig();
  const plugins = await loadPlugins(config);
  const engine = new SsgEngine(plugins, options, config);
  return engine.build();
}
