import fs from 'fs';
import path from 'path';
import { Page, BuildResult } from './types';

export interface PluginContext {
  contentDir: string;
  outputDir: string;
  templatesDir: string;
  config: Record<string, unknown>;
  pages: Page[];
  files: string[];
  rebuild?: () => void;
}

export type PluginHook =
  | 'onStart'
  | 'beforeBuild'
  | 'afterBuild'
  | 'onFile'
  | 'onEnd';

export interface Plugin {
  name: string;
  onStart?: (ctx: PluginContext) => void;
  beforeBuild?: (ctx: PluginContext) => void;
  afterBuild?: (ctx: PluginContext, result: BuildResult) => void;
  onFile?: (page: Page, ctx: PluginContext) => Page | void;
  onEnd?: (ctx: PluginContext) => void;
}

export function runHook(
  plugin: Plugin,
  hook: PluginHook,
  ctx: PluginContext,
  result?: BuildResult
): void {
  if (hook === 'afterBuild') {
    if (typeof plugin.afterBuild === 'function') {
      plugin.afterBuild.call(plugin, ctx, result as BuildResult);
    }
    return;
  }
  if (hook === 'onFile') {
    if (typeof plugin.onFile === 'function') {
      const page = ctx.pages && ctx.pages.length > 0 ? ctx.pages[0] : ({} as Page);
      plugin.onFile.call(plugin, page, ctx);
    }
    return;
  }
  const fn = plugin[hook];
  if (typeof fn === 'function') {
    fn.call(plugin, ctx);
  }
}

export function runHooks(
  plugins: Plugin[],
  hook: PluginHook,
  ctx: PluginContext,
  result?: BuildResult
): void {
  for (const plugin of plugins) {
    runHook(plugin, hook, ctx, result);
  }
}

function isPluginObject(value: unknown): value is Plugin {
  if (!value || typeof value !== 'object' || typeof value === 'function') {
    return false;
  }
  const maybe = value as Partial<Plugin>;
  return typeof maybe.name === 'string' && maybe.name.length > 0;
}

function resolveModulePath(cwd: string, spec: string): string {
  const base = path.resolve(cwd);
  let full = path.isAbsolute(spec) ? spec : path.resolve(base, spec);

  const candidates: string[] = [];
  if (!path.extname(full)) {
    for (const ext of ['.ts', '.js', '.cjs', '.mjs']) candidates.push(full + ext);
    candidates.push(path.join(full, 'index.ts'));
    candidates.push(path.join(full, 'index.js'));
  } else {
    candidates.push(full);
  }
  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) return candidate;
  }
  return full;
}

export function loadPluginModule(
  cwd: string,
  spec: string | { path?: string; module?: string }
): Plugin | null {
  const rel =
    typeof spec === 'string' ? spec : (spec.path ?? spec.module ?? '');
  if (!rel) return null;

  let full = path.isAbsolute(rel) ? rel : path.resolve(cwd, rel);
  if (!fs.existsSync(full)) {
    const inPlugins = path.resolve(cwd, 'plugins', rel);
    if (fs.existsSync(inPlugins) || fs.existsSync(resolveModulePath(cwd, inPlugins))) {
      full = inPlugins;
    } else {
      full = resolveModulePath(cwd, rel);
    }
  }
  if (!fs.existsSync(full)) return null;

  const mod = require(full) as {
    default?: unknown;
    [key: string]: unknown;
  };
  return toPlugin(mod.default ?? mod);
}

export function toPlugin(value: unknown): Plugin | null {
  if (value == null) return null;
  if (isPluginObject(value)) return value;
  if (typeof value === 'function') {
    try {
      const instance = new (value as new () => Plugin)();
      return isPluginObject(instance) ? instance : null;
    } catch {
      return null;
    }
  }
  if (typeof value === 'string') {
    return null;
  }
  return null;
}

export function loadConfig(cwd: string, configFile?: string): Record<string, unknown> {
  const name = configFile ?? 'ssg.config.ts';
  const resolved = resolveModulePath(cwd, name);
  if (!fs.existsSync(resolved)) return {};
  const mod = require(resolved) as {
    default?: Record<string, unknown>;
    [key: string]: unknown;
  };
  const cfg = (mod.default ?? mod) as Record<string, unknown>;
  return cfg && typeof cfg === 'object' ? cfg : {};
}

export function pluginsFromConfig(config: Record<string, unknown>): Plugin[] {
  const raw = config.plugins;
  if (!Array.isArray(raw)) return [];
  const plugins: Plugin[] = [];
  for (const entry of raw) {
    const plugin = toPlugin(entry);
    if (plugin) {
      plugins.push(plugin);
    } else if (typeof entry === 'string') {
      const loaded = loadPluginModule(process.cwd(), entry);
      if (loaded) plugins.push(loaded);
    }
  }
  return plugins;
}

export function discoverPlugins(cwd: string): Plugin[] {
  const dir = path.resolve(cwd, 'plugins');
  if (!fs.existsSync(dir)) return [];
  const plugins: Plugin[] = [];
  const entries = fs.readdirSync(dir).sort();
  for (const entry of entries) {
    if (!/\.(ts|js|cjs|mjs)$/.test(entry)) continue;
    if (/\.(test|spec)\./.test(entry)) continue;
    if (entry === 'index.ts' || entry === 'index.js') continue;
    const full = path.join(dir, entry);
    const mod = require(full) as {
      default?: unknown;
      [key: string]: unknown;
    };
    const plugin = toPlugin(mod.default ?? mod);
    if (plugin) plugins.push(plugin);
  }
  return plugins;
}
