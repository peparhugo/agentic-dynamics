import fs from 'fs/promises';
import nodeFs, { Dirent } from 'fs';
import path from 'path';
import { Plugin, PluginHook } from './plugin';

export interface SsgConfig {
  plugins?: PluginEntry[];
}

export type PluginEntry = Plugin | string | (() => Plugin | Promise<Plugin>);

const DEFAULT_PLUGINS_DIR = 'plugins';
const HOOKS: PluginHook[] = ['onStart', 'beforeBuild', 'afterBuild', 'onFile', 'onEnd'];

async function exists(filePath: string): Promise<boolean> {
  try {
    await fs.stat(filePath);
    return true;
  } catch {
    return false;
  }
}

function installTsSupport(): void {
  const extensions = (require as unknown as { extensions: Record<string, unknown> }).extensions;
  if (extensions['.ts']) return;

  const ts = require('typescript');
  extensions['.ts'] = function (module: { _compile: (code: string, file: string) => void }, filename: string): void {
    const source = nodeFs.readFileSync(filename, 'utf-8');
    const result = ts.transpileModule(source, {
      compilerOptions: {
        module: ts.ModuleKind.CommonJS,
        target: ts.ScriptTarget.ES2020,
        esModuleInterop: true,
        moduleResolution: ts.ModuleResolutionKind.NodeJs,
      },
      fileName: filename,
    });
    module._compile(result.outputText, filename);
  };

  const Module = require('module') as {
    _resolveFilename: (
      request: string,
      parent: { filename?: string } | undefined,
      isMain: boolean,
      options?: unknown
    ) => string;
  };
  const originalResolve = Module._resolveFilename;
  Module._resolveFilename = function (
    request: string,
    parent: { filename?: string } | undefined,
    isMain: boolean,
    options?: unknown
  ): string {
    try {
      return originalResolve.call(this, request, parent, isMain, options);
    } catch (err) {
      if (parent && parent.filename && parent.filename.endsWith('.ts') && !path.extname(request)) {
        return originalResolve.call(this, `${request}.ts`, parent, isMain, options);
      }
      throw err;
    }
  };
}

function requireModule(filePath: string): unknown {
  if (filePath.endsWith('.ts')) {
    installTsSupport();
  }
  const mod = require(filePath) as { default?: unknown };
  return (mod && mod.default !== undefined ? mod.default : mod) as unknown;
}

function hasHook(candidate: unknown): boolean {
  const record = candidate as Record<string, unknown>;
  return HOOKS.some((hook) => typeof record?.[hook] === 'function');
}

function instantiate(candidate: unknown): unknown {
  if (candidate && typeof candidate === 'function') {
    try {
      return new (candidate as new () => unknown)();
    } catch {
      try {
        return (candidate as () => unknown)();
      } catch {
        return undefined;
      }
    }
  }
  return candidate;
}

function toPlugin(candidate: unknown): Plugin | undefined {
  const instance = instantiate(candidate);
  if (
    instance &&
    typeof instance === 'object' &&
    typeof (instance as Plugin).name === 'string' &&
    hasHook(instance)
  ) {
    return instance as Plugin;
  }
  return undefined;
}

function resolvePluginPath(entry: string, dir: string): string {
  if (path.isAbsolute(entry)) return entry;
  if (entry.startsWith('.')) return path.resolve(dir, entry);
  return path.resolve(dir, DEFAULT_PLUGINS_DIR, entry);
}

async function normalizeEntry(entry: PluginEntry, dir: string): Promise<Plugin | undefined> {
  if (typeof entry === 'string') {
    const mod = requireModule(resolvePluginPath(entry, dir));
    return toPlugin(mod);
  }
  if (typeof entry === 'function') {
    const candidate = await entry();
    return toPlugin(candidate);
  }
  return toPlugin(entry);
}

async function discoverPlugins(dir: string): Promise<Plugin[]> {
  const pluginsDir = path.join(dir, DEFAULT_PLUGINS_DIR);
  if (!(await exists(pluginsDir))) return [];

  let entries: Dirent[];
  try {
    entries = await fs.readdir(pluginsDir, { withFileTypes: true });
  } catch {
    return [];
  }

  const discovered: Plugin[] = [];
  for (const entry of entries) {
    if (!entry.isFile()) continue;
    if (!/\.(ts|js|mjs)$/.test(entry.name)) continue;
    let mod: unknown;
    try {
      mod = requireModule(path.join(pluginsDir, entry.name));
    } catch {
      continue;
    }
    const plugin = toPlugin(mod);
    if (plugin) discovered.push(plugin);
  }
  return discovered;
}

export async function loadConfig(dir: string = process.cwd()): Promise<SsgConfig> {
  const tsPath = path.join(dir, 'ssg.config.ts');
  const jsPath = path.join(dir, 'ssg.config.js');
  if (await exists(jsPath)) {
    const mod = requireModule(jsPath);
    return (mod as SsgConfig) ?? {};
  }
  if (await exists(tsPath)) {
    const mod = requireModule(tsPath);
    return (mod as SsgConfig) ?? {};
  }
  return {};
}

export async function loadConfiguredPlugins(
  dir: string = process.cwd()
): Promise<{ plugins: Plugin[]; config: SsgConfig }> {
  const config = await loadConfig(dir);
  const plugins: Plugin[] = [];
  const seen = new Set<string>();

  function add(plugin: Plugin | undefined): void {
    if (!plugin || seen.has(plugin.name)) return;
    seen.add(plugin.name);
    plugins.push(plugin);
  }

  for (const entry of config.plugins ?? []) {
    add(await normalizeEntry(entry, dir));
  }
  for (const plugin of await discoverPlugins(dir)) {
    add(plugin);
  }
  return { plugins, config };
}
