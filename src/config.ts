import fs from 'fs';
import path from 'path';
import { Plugin } from './plugin';
import { builtinPlugins } from './plugins';

export interface SSGConfig {
  plugins: Plugin[];
}

export const DEFAULT_CONFIG_FILE = 'ssg.config.ts';

export function resolveConfigPath(configPath?: string): string {
  return configPath
    ? path.resolve(process.cwd(), configPath)
    : path.resolve(process.cwd(), DEFAULT_CONFIG_FILE);
}

export function loadConfig(configPath?: string): SSGConfig {
  const resolved = resolveConfigPath(configPath);
  if (!fs.existsSync(resolved)) {
    return { plugins: builtinPlugins() };
  }
  try {
    const mod = require(resolved);
    const exported = (mod && mod.default) ?? mod;
    const cfg = typeof exported === 'function' ? exported() : exported;
    if (cfg && Array.isArray(cfg.plugins) && cfg.plugins.length > 0) {
      return cfg as SSGConfig;
    }
    return { plugins: builtinPlugins() };
  } catch {
    return { plugins: builtinPlugins() };
  }
}
