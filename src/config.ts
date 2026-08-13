import fs from 'fs';
import path from 'path';
import type { Plugin } from './plugin';
import { MarkdownPlugin } from './plugins/MarkdownPlugin';
import { TemplatePlugin } from './plugins/TemplatePlugin';

export interface SsgConfig {
  plugins?: PluginEntry[];
}

export type PluginEntry = Plugin | PluginConstructor;

export interface PluginConstructor {
  new (): Plugin;
}

export function defaultPlugins(): Plugin[] {
  return [new MarkdownPlugin(), new TemplatePlugin()];
}

export function resolvePluginEntry(entry: PluginEntry): Plugin {
  if (typeof entry === 'function') {
    const PluginClass = entry as PluginConstructor;
    return new PluginClass();
  }
  return entry;
}

export function loadConfig(configPath = 'ssg.config.ts'): SsgConfig | undefined {
  const resolved = path.resolve(configPath);
  if (!fs.existsSync(resolved)) {
    return undefined;
  }
  try {
    const mod = require(resolved) as SsgConfig | { default: SsgConfig };
    return mod && typeof mod === 'object' && 'default' in mod
      ? (mod as { default: SsgConfig }).default
      : (mod as SsgConfig);
  } catch {
    return undefined;
  }
}

export function loadPluginsFromConfig(configPath = 'ssg.config.ts'): Plugin[] {
  const config = loadConfig(configPath);
  if (!config || !Array.isArray(config.plugins) || config.plugins.length === 0) {
    return defaultPlugins();
  }
  return config.plugins.map(resolvePluginEntry);
}
