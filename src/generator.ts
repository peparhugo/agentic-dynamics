import { loadConfig } from './config';
import { loadPlugins } from './loader';
import { SsgEngine } from './engine';
import { BuildOptions, BuildStats, Page } from './types';

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

export interface BuildResult {
  pages: Page[];
  stats: BuildStats;
}

/**
 * Build a static site and return the generated pages together with the build
 * statistics (pages built, skipped, and time saved by incremental caching).
 */
export async function buildWithStats(options: BuildOptions): Promise<BuildResult> {
  const config = await loadConfig();
  const plugins = await loadPlugins(config);
  const engine = new SsgEngine(plugins, options, config);
  const pages = await engine.build();
  return { pages, stats: engine.getStats() };
}
