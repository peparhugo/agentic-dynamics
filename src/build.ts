import { SSGEngine } from './core';
import { loadPluginsFromConfig } from './config';
import type { Plugin } from './plugin';
import type { Page } from './types';

export interface SiteBuildResult {
  outputDir: string;
  pages: Page[];
  indexFile: string;
}

export { slugify } from './core';

export interface BuildSiteOptions {
  plugins?: Plugin[];
}

export function buildSite(
  contentDir: string,
  outputDir: string,
  templatesDir = 'templates',
  options: BuildSiteOptions = {},
): SiteBuildResult {
  const plugins = options.plugins ?? loadPluginsFromConfig();
  const engine = new SSGEngine({ contentDir, outputDir, templatesDir, plugins });
  engine.start();
  try {
    return engine.build();
  } finally {
    engine.stop();
  }
}
