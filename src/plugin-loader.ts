import fs from 'fs';
import path from 'path';
import ts from 'typescript';
import type { Plugin, SSGConfig } from './types';
import { PLUGIN_HOOKS } from './types';

export const DEFAULT_CONFIG_FILE = 'ssg.config.ts';
export const DEFAULT_PLUGINS_DIR = './plugins';

export function ensureTypeScriptLoader(): void {
  if (require.extensions['.ts'] !== undefined) return;
  require.extensions['.ts'] = (module: NodeModule, filename: string) => {
    const source = fs.readFileSync(filename, 'utf8');
    const { outputText } = ts.transpileModule(source, {
      fileName: filename,
      compilerOptions: {
        module: ts.ModuleKind.CommonJS,
        target: ts.ScriptTarget.ES2020,
        esModuleInterop: true,
        moduleResolution: ts.ModuleResolutionKind.NodeJs,
      },
    });
    (module as unknown as { _compile(code: string, fileName: string): void })._compile(outputText, filename);
  };
}

export function loadTsModule(filename: string): unknown {
  ensureTypeScriptLoader();
  return require(filename);
}

export function resolveConfigPath(configPath?: string): string | null {
  const candidate = configPath ? path.resolve(configPath) : path.resolve(DEFAULT_CONFIG_FILE);
  return fs.existsSync(candidate) && fs.statSync(candidate).isFile() ? candidate : null;
}

export function normalizeConfig(value: unknown): SSGConfig {
  const mod = (value as { default?: unknown } | null)?.default ?? value;
  if (mod && typeof mod === 'object' && !Array.isArray(mod)) {
    const plugins = (mod as Partial<SSGConfig>).plugins;
    return { plugins: Array.isArray(plugins) ? plugins.map(String) : [] };
  }
  return { plugins: [] };
}

export function loadConfig(configPath?: string): SSGConfig {
  const resolved = resolveConfigPath(configPath);
  if (!resolved) return { plugins: [] };
  return normalizeConfig(loadTsModule(resolved));
}

export function toPlugin(value: unknown, name?: string): Plugin | null {
  const mod = (value as { default?: unknown } | null)?.default ?? value;
  let candidate = mod;
  if (typeof candidate === 'function') {
    const proto = (candidate as { prototype?: object }).prototype;
    const isClass =
      !!proto && PLUGIN_HOOKS.some((hook) => typeof (proto as Record<string, unknown>)[hook] === 'function');
    try {
      candidate = isClass ? new (candidate as new () => unknown)() : (candidate as () => unknown)();
    } catch {
      return null;
    }
  }
  if (!candidate || typeof candidate !== 'object') return null;
  const plugin = candidate as Plugin;
  if (typeof plugin.name !== 'string' || plugin.name.trim() === '') {
    plugin.name = name?.trim() || 'anonymous';
  }
  return plugin;
}

export function loadPlugin(spec: string, baseDir: string = process.cwd()): Plugin | null {
  ensureTypeScriptLoader();
  try {
    if (spec.startsWith('./') || spec.startsWith('../') || path.isAbsolute(spec)) {
      let target = path.resolve(baseDir, spec);
      if (!fs.existsSync(target)) {
        if (fs.existsSync(target + '.ts')) target += '.ts';
        else if (fs.existsSync(target + '.js')) target += '.js';
        else if (fs.existsSync(path.join(target, 'index.ts'))) target = path.join(target, 'index.ts');
        else if (fs.existsSync(path.join(target, 'index.js'))) target = path.join(target, 'index.js');
      }
      if (!fs.existsSync(target)) return null;
      return toPlugin(require(target), spec);
    }
    return toPlugin(require(spec), spec);
  } catch {
    return null;
  }
}

export function loadPluginsFromConfig(config: SSGConfig, baseDir: string = process.cwd()): Plugin[] {
  const plugins: Plugin[] = [];
  for (const entry of config.plugins ?? []) {
    const plugin = loadPlugin(entry, baseDir);
    if (plugin) plugins.push(plugin);
  }
  return plugins;
}
