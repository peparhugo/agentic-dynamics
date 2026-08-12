import { SSGEngine } from './engine';
import { loadConfig } from './config';
import { BuildOptions, Page } from './types';

export { BuildOptions } from './types';

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

export { SSGEngine } from './engine';
