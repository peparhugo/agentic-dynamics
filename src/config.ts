/**
 * Plugin configuration loading.
 *
 * Plugins are configured through a `ssg.config.ts` (or `.js`) file in the
 * working directory. The file's default export is an object whose `plugins`
 * array lists built-in plugin names and/or paths to TypeScript plugin modules
 * under `./plugins/`.
 */

import fs from 'fs';
import path from 'path';

import { DevServerPlugin } from './plugins/dev-server';
import { MarkdownPlugin } from './plugins/markdown';
import { TemplatePlugin } from './plugins/template';
import type { Plugin } from './plugin';
import type { BuildOptions } from './types';

/** Default config file name. */
export const DEFAULT_CONFIG_FILE = 'ssg.config.ts';

/** A config `plugins` entry: a built-in name, a module path, or a plugin. */
export type PluginSpec = string | Plugin | (() => Plugin);

/** Shape of the SSG config file. */
export interface SSGConfig {
  /** Plugins to load, in execution order (after the built-in plugins). */
  plugins?: PluginSpec[];
  [key: string]: unknown;
}

/** A config file together with the directory it was loaded from. */
export interface LoadedConfig {
  /** The parsed configuration object. */
  config: SSGConfig;
  /** Directory containing the config file (base for relative paths). */
  dir: string;
}

/** Resolve the config file path, defaulting to `./ssg.config.ts`. */
export function resolveConfigPath(configPath?: string): string {
  if (configPath) return path.resolve(configPath);
  const tsPath = path.resolve(DEFAULT_CONFIG_FILE);
  if (fs.existsSync(tsPath)) return tsPath;
  const jsPath = tsPath.replace(/\.ts$/, '.js');
  return fs.existsSync(jsPath) ? jsPath : tsPath;
}

/**
 * Load the SSG config. Missing config files (or files that cannot be loaded,
 * e.g. an uncompiled `.ts` file at runtime) yield an empty config.
 */
export function loadConfig(configPath?: string): LoadedConfig {
  const resolved = resolveConfigPath(configPath);
  const dir = path.dirname(resolved);

  if (!fs.existsSync(resolved)) {
    return { config: {}, dir };
  }

  let config = loadModule<SSGConfig>(resolved);
  if (config === null && resolved.endsWith('.ts')) {
    const jsPath = resolved.slice(0, -3) + '.js';
    if (fs.existsSync(jsPath)) {
      config = loadModule<SSGConfig>(jsPath);
    }
  }

  return { config: config ?? {}, dir };
}

/** Require a module, normalising a default export, or null on failure. */
function loadModule<T>(modulePath: string): T | null {
  try {
    const resolved = require.resolve(modulePath);
    delete require.cache[resolved];
    const mod = require(modulePath) as unknown;
    const value = (mod as { default?: T } | null)?.default ?? mod;
    return value as T;
  } catch {
    return null;
  }
}

/** Resolve a single plugin spec into a Plugin instance. */
export function resolvePluginSpec(spec: PluginSpec, baseDir: string): Plugin {
  if (typeof spec !== 'string') {
    return typeof spec === 'function' ? spec() : spec;
  }

  const builtin = BUILTIN_PLUGIN_FACTORIES[spec];
  if (builtin) return builtin();

  const modulePath = resolvePluginModule(spec, baseDir);
  if (!modulePath) {
    throw new Error(`Plugin module not found: ${spec} (searched under ${baseDir})`);
  }

  const mod = require(modulePath) as unknown;
  const value = (mod as { default?: unknown } | null)?.default ?? mod;
  if (typeof value === 'function') {
    return (value as () => Plugin)();
  }
  return value as Plugin;
}

/** Resolve a plugin module specifier to a loadable file path. */
function resolvePluginModule(spec: string, baseDir: string): string | null {
  const resolved = path.resolve(baseDir, spec);
  const candidates: string[] = [resolved];

  if (!path.extname(resolved)) {
    candidates.push(`${resolved}.ts`, `${resolved}.js`, `${resolved}.cjs`);
  }

  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) return candidate;
  }
  return null;
}

/** The built-in plugins available to every build. */
export function builtinPlugins(): Plugin[] {
  return [new MarkdownPlugin(), new TemplatePlugin()];
}

/**
 * Assemble the full plugin list for a build: the built-in markdown and
 * template plugins first, then any plugins listed in the config file, then
 * any plugins passed directly through the build options.
 */
export function loadPlugins(
  loaded: LoadedConfig,
  options?: BuildOptions,
): Plugin[] {
  const plugins: Plugin[] = builtinPlugins();

  for (const spec of loaded.config.plugins ?? []) {
    plugins.push(resolvePluginSpec(spec, loaded.dir));
  }

  for (const plugin of options?.plugins ?? []) {
    plugins.push(plugin);
  }

  return plugins;
}

const BUILTIN_PLUGIN_FACTORIES: Record<string, () => Plugin> = {
  markdown: () => new MarkdownPlugin(),
  templates: () => new TemplatePlugin(),
  'dev-server': () => new DevServerPlugin(),
};
