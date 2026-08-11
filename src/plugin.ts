import path from 'path';
import { Plugin } from './types';

export type { Plugin };

let cachedPlugins: Plugin[] | null = null;

export function loadPlugins(): Plugin[] {
  if (cachedPlugins) return cachedPlugins;

  const configPath = path.resolve(process.cwd(), 'ssg.config');
  try {
    const mod = require(configPath);
    const config = mod.default || mod;
    if (Array.isArray(config.plugins)) {
      cachedPlugins = config.plugins;
      return cachedPlugins as Plugin[];
    }
  } catch {
    // config not found, use built-ins
  }

  const { builtInPlugins } = require('./plugins');
  cachedPlugins = builtInPlugins;
  return cachedPlugins as Plugin[];
}

export function setPlugins(plugins: Plugin[]): void {
  cachedPlugins = plugins;
}
