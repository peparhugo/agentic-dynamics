import { existsSync } from 'fs';
import { dirname, join, resolve } from 'path';
import { isPlugin, Plugin } from './plugin';
import { DevServerPlugin } from './plugins/dev-server';
import { MarkdownPlugin } from './plugins/markdown';
import { TemplatePlugin } from './plugins/template';

const CONFIG_FILENAMES = ['ssg.config.ts', 'ssg.config.js', 'ssg.config.cjs'];

const BUILTIN_PLUGINS: Record<string, () => Plugin> = {
  markdown: () => new MarkdownPlugin(),
  template: () => new TemplatePlugin(),
  'dev-server': () => new DevServerPlugin(),
  'live-reload': () => new DevServerPlugin(),
};

export function findConfigFile(baseDir: string = process.cwd()): string | null {
  for (const name of CONFIG_FILENAMES) {
    const candidate = join(baseDir, name);
    if (existsSync(candidate)) return candidate;
  }
  return null;
}

function loadModule(configPath: string): unknown {
  const loaded = require(configPath) as unknown;
  if (loaded !== null && typeof loaded === 'object' && 'default' in loaded) {
    return (loaded as { default: unknown }).default;
  }
  return loaded;
}

function extractPluginEntries(value: unknown): unknown[] {
  if (Array.isArray(value)) return value;
  if (value !== null && typeof value === 'object') {
    const record = value as Record<string, unknown>;
    if (Array.isArray(record.plugins)) return record.plugins;
    if (record.plugins !== undefined && record.plugins !== null) return [record.plugins];
    return [record];
  }
  return [];
}

function resolvePluginEntry(entry: unknown, baseDir: string): Plugin | null {
  if (typeof entry === 'string') return resolvePluginName(entry, baseDir);

  let candidate: unknown = entry;
  if (typeof entry === 'function') {
    try {
      candidate = new (entry as new () => unknown)();
    } catch {
      try {
        candidate = (entry as () => unknown)();
      } catch {
        return null;
      }
    }
  }

  if (candidate !== null && typeof candidate === 'object' && isPlugin(candidate)) {
    const plugin = candidate as Plugin;
    if (plugin.name.length === 0) {
      const source = entry as { name?: string };
      return { ...plugin, name: source.name || 'unnamed' };
    }
    return plugin;
  }
  return null;
}

function resolvePluginName(name: string, baseDir: string): Plugin | null {
  const builtin = BUILTIN_PLUGINS[name];
  if (builtin) return builtin();

  const bases = [join(baseDir, 'plugins', name), join(baseDir, name)];
  const seen = new Set<string>();
  for (const base of bases) {
    for (const suffix of ['', '.ts', '.js', '.cjs', '/index.ts', '/index.js']) {
      const target = base + suffix;
      if (seen.has(target)) continue;
      seen.add(target);
      if (!existsSync(target)) continue;
      const loaded = loadModule(target);
      const resolved = resolvePluginEntry(loaded, dirname(target));
      if (resolved) return resolved;
    }
  }
  return null;
}

export function loadPlugins(configPath?: string): Plugin[] {
  const resolvedPath = configPath ? resolve(configPath) : findConfigFile();
  if (!resolvedPath || !existsSync(resolvedPath)) return [];
  try {
    const value = loadModule(resolvedPath);
    const entries = extractPluginEntries(value);
    const plugins: Plugin[] = [];
    for (const entry of entries) {
      const plugin = resolvePluginEntry(entry, dirname(resolvedPath));
      if (plugin) plugins.push(plugin);
    }
    return plugins;
  } catch {
    return [];
  }
}
