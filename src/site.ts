import * as path from 'path';
import { DEFAULT_CACHE_FILENAME } from './cache';
import { loadConfig } from './config';
import { BuildStats, SSGEngine } from './engine';
import { Page } from './page';
import { Plugin } from './plugin';

export interface BuildOptions {
  contentDir: string;
  outputDir: string;
  templatesDir?: string;
  /** Overrides the plugin pipeline instead of loading it from ssg.config.ts. */
  plugins?: Plugin[];
  /** Path to a config file to load plugins from; defaults to ssg.config.ts. */
  configPath?: string;
  /** When true, pages whose source and templates are unchanged since the last build are skipped. */
  incremental?: boolean;
  /** When true (with `incremental`), ignores any existing build cache and rebuilds every page. */
  clean?: boolean;
  /** Path to the incremental build manifest; defaults to `.ssg-cache.json` inside `outputDir`. */
  cachePath?: string;
}

export interface BuildResult {
  pages: Page[];
  outputDir: string;
  /** Incremental build stats, or null when `incremental` wasn't requested. */
  stats: BuildStats | null;
}

export function buildSite(options: BuildOptions): BuildResult {
  const contentDir = path.resolve(options.contentDir);
  const outputDir = path.resolve(options.outputDir);
  const templatesDir = path.resolve(options.templatesDir ?? './templates');
  const cachePath = path.resolve(options.cachePath ?? path.join(outputDir, DEFAULT_CACHE_FILENAME));

  const plugins = options.plugins ?? loadConfig(options.configPath).plugins;

  const engine = new SSGEngine({
    contentDir,
    outputDir,
    templatesDir,
    plugins,
    incremental: options.incremental,
    clean: options.clean,
    cachePath,
  });
  const pages = engine.run();

  return { pages, outputDir, stats: engine.lastBuildStats };
}
