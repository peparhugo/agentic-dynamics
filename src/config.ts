import path from 'path';
import { existsSync } from 'fs';
import type { Plugin } from './plugin';
import { isPlugin } from './plugin';
import { loadModule } from './loaders';

export interface SsgConfig {
  plugins?: Array<Plugin | string>;
}

export function defineConfig(config: SsgConfig): SsgConfig {
  return config;
}

export function normalizeConfig(raw: unknown): SsgConfig {
  if (!raw || typeof raw !== 'object') {
    return {};
  }
  const config = raw as SsgConfig;
  if (config.plugins == null) {
    return {};
  }
  const plugins = Array.isArray(config.plugins) ? config.plugins : [config.plugins];
  return { plugins };
}

const CONFIG_FILENAMES = [
  'ssg.config.ts',
  'ssg.config.mts',
  'ssg.config.js',
  'ssg.config.cjs',
  'ssg.config.mjs',
  'ssg.config.json',
];

export async function loadConfig(cwd: string = process.cwd()): Promise<SsgConfig> {
  for (const name of CONFIG_FILENAMES) {
    const filePath = path.join(cwd, name);
    if (!existsSync(filePath)) {
      continue;
    }
    try {
      const loaded = await loadModule(filePath);
      const exported = unwrapDefault(loaded);
      const resolved = typeof exported === 'function' ? await exported() : exported;
      return normalizeConfig(resolved);
    } catch {
      continue;
    }
  }
  return {};
}

export async function loadConfigFile(filePath: string): Promise<SsgConfig> {
  const loaded = await loadModule(path.resolve(filePath));
  const exported = unwrapDefault(loaded);
  const resolved = typeof exported === 'function' ? await exported() : exported;
  return normalizeConfig(resolved);
}

function unwrapDefault(mod: unknown): unknown {
  if (mod && typeof mod === 'object' && 'default' in (mod as Record<string, unknown>)) {
    return (mod as { default: unknown }).default;
  }
  return mod;
}

const BUILTIN_PLUGIN_NAMES = new Set(['markdown', 'template', 'devServer']);

export async function resolvePlugins(
  entries: Array<Plugin | string> | undefined,
  baseDir: string
): Promise<Plugin[]> {
  const resolved: Plugin[] = [];
  for (const entry of entries ?? []) {
    for (const plugin of await resolvePluginEntry(entry, baseDir)) {
      resolved.push(plugin);
    }
  }
  return resolved;
}

async function resolvePluginEntry(
  entry: Plugin | string,
  baseDir: string
): Promise<Plugin[]> {
  if (typeof entry === 'string') {
    if (BUILTIN_PLUGIN_NAMES.has(entry)) {
      return [];
    }
    const filePath = resolvePluginPath(baseDir, entry);
    if (!filePath) {
      return [];
    }
    try {
      return await flattenPluginExport(await loadModule(filePath));
    } catch {
      return [];
    }
  }
  if (typeof entry === 'function') {
    return flattenPluginExport(await (entry as () => unknown)());
  }
  if (isPlugin(entry)) {
    return [entry];
  }
  return [];
}

function resolvePluginPath(baseDir: string, entry: string): string | undefined {
  const abs = path.isAbsolute(entry) ? entry : path.resolve(baseDir, entry);
  const candidates = [
    abs,
    `${abs}.ts`,
    `${abs}.tsx`,
    `${abs}.js`,
    `${abs}.cjs`,
    `${abs}.mjs`,
    path.join(abs, 'index.ts'),
    path.join(abs, 'index.js'),
    path.join(abs, 'index.json'),
  ];
  for (const candidate of candidates) {
    if (existsSync(candidate)) {
      return candidate;
    }
  }
  return undefined;
}

async function flattenPluginExport(mod: unknown): Promise<Plugin[]> {
  const exported = unwrapDefault(mod);
  if (typeof exported === 'function') {
    return flattenPluginExport(await (exported as () => unknown)());
  }
  if (Array.isArray(exported)) {
    const out: Plugin[] = [];
    for (const item of exported) {
      out.push(...(await flattenPluginExport(item)));
    }
    return out;
  }
  if (isPlugin(exported)) {
    return [exported];
  }
  return [];
}
