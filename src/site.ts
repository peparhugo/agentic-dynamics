import * as path from 'path';
import { loadConfig } from './config';
import { SSGEngine } from './engine';
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
}

export interface BuildResult {
  pages: Page[];
  outputDir: string;
}

export function buildSite(options: BuildOptions): BuildResult {
  const contentDir = path.resolve(options.contentDir);
  const outputDir = path.resolve(options.outputDir);
  const templatesDir = path.resolve(options.templatesDir ?? './templates');

  const plugins = options.plugins ?? loadConfig(options.configPath).plugins;

  const engine = new SSGEngine({ contentDir, outputDir, templatesDir, plugins });
  const pages = engine.run();

  return { pages, outputDir };
}
