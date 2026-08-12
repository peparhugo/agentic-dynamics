import { Page, BuildOptions, BuildStats, IncrementalBuildOptions } from './types';
import { SSG } from './engine';
import { builtinPlugins } from './plugins';

export { collectPages } from './collect';

export function buildSite(options: BuildOptions, buildOptions?: IncrementalBuildOptions): Page[] {
  const engine = new SSG({ options, plugins: builtinPlugins() });
  engine.start();
  return engine.build(buildOptions);
}

export function buildSiteWithStats(
  options: BuildOptions,
  buildOptions?: IncrementalBuildOptions
): { pages: Page[]; stats: BuildStats } {
  const engine = new SSG({ options, plugins: builtinPlugins() });
  engine.start();
  const pages = engine.build(buildOptions);
  return { pages, stats: engine.lastBuildStats as BuildStats };
}
