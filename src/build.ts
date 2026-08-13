import { SSGEngine } from './core';
import { loadPluginsFromConfig } from './config';
import type { Plugin } from './plugin';
import type { Page } from './types';
import type { BuildStats } from './cache';

export interface SiteBuildResult {
  outputDir: string;
  pages: Page[];
  indexFile: string;
  stats: BuildStats;
}

export { slugify } from './core';

export interface BuildSiteOptions {
  plugins?: Plugin[];
  incremental?: boolean;
  clean?: boolean;
}

export function buildSite(
  contentDir: string,
  outputDir: string,
  templatesDir = 'templates',
  options: BuildSiteOptions = {},
): SiteBuildResult {
  const plugins = options.plugins ?? loadPluginsFromConfig();
  const engine = new SSGEngine({
    contentDir,
    outputDir,
    templatesDir,
    plugins,
    incremental: options.incremental,
    clean: options.clean,
  });
  engine.start();
  try {
    return engine.build();
  } finally {
    engine.stop();
  }
}
