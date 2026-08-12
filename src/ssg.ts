import { SSGEngine } from './engine';
import { loadConfig } from './config';
import { BuildOptions, BuildStats, Page } from './types';

export { BuildOptions, BuildStats } from './types';

/**
 * Build the static site. Plugins are loaded from ssg.config.ts (or the given
 * configPath); the built-in markdown and template plugins are always included.
 * Returns the parsed pages.
 */
export function build(options: BuildOptions = {}): Page[] {
  const config = options.plugins ? { plugins: options.plugins } : loadConfig(options.configPath);
  const engine = new SSGEngine(config);
  return engine.build(options);
}

/**
 * Build the static site with caching enabled. Unchanged pages (same source and
 * template hashes) are skipped and reused from the `.ssg-cache.json` manifest.
 * Returns the parsed pages along with build statistics.
 */
export function buildIncremental(options: BuildOptions = {}): { pages: Page[]; stats: BuildStats } {
  const config = options.plugins ? { plugins: options.plugins } : loadConfig(options.configPath);
  const engine = new SSGEngine(config);
  const pages = engine.build({ ...options, incremental: true });
  return {
    pages,
    stats: engine.lastStats ?? {
      total: pages.length,
      built: pages.length,
      skipped: 0,
      timeSaved: 0,
    },
  };
}

export { SSGEngine } from './engine';
