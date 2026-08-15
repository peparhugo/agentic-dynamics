import * as path from 'path';
import { Plugin } from './plugin';
import { markdownPlugin } from '../plugins/markdown-plugin';
import { templatePlugin } from '../plugins/template-plugin';

export interface SSGConfig {
  plugins: Plugin[];
}

function builtInDefaultPlugins(): Plugin[] {
  return [markdownPlugin(), templatePlugin()];
}

function defaultConfigPath(): string {
  return path.resolve(__dirname, '..', 'ssg.config');
}

/**
 * Loads the plugin pipeline from `ssg.config.ts` (or a custom path). Falls
 * back to the built-in markdown + template plugins whenever no config file
 * is present, or the file exists but doesn't export a usable plugin list -
 * this keeps `buildSite`/`startDevServer` working with zero configuration.
 */
export function loadConfig(configPath?: string): SSGConfig {
  const resolvedPath = configPath ? path.resolve(configPath) : defaultConfigPath();

  try {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const mod = require(resolvedPath);
    const config = (mod?.default ?? mod) as Partial<SSGConfig> | undefined;
    if (config && Array.isArray(config.plugins) && config.plugins.length > 0) {
      return { plugins: config.plugins };
    }
  } catch {
    // No config file at this path, or it failed to load - use the built-ins.
  }

  return { plugins: builtInDefaultPlugins() };
}
