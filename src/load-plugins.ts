import * as fs from 'fs';
import * as path from 'path';
import { Plugin } from './plugin';

export type PluginModule = Plugin | (new () => Plugin) | string;

export interface SSGConfig {
  plugins?: PluginModule[];
}

interface CompiledModule {
  filename: string;
  paths: string[];
  _compile: (code: string, filename: string) => void;
  exports: unknown;
}

function transpile(source: string): string {
  const ts = require('typescript');
  return ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2020,
      esModuleInterop: true,
    },
  }).outputText;
}

function loadTsModule(filePath: string): unknown {
  const source = fs.readFileSync(filePath, 'utf8');
  const js = transpile(source);

  const ModuleCtor = require('module');
  const mod: CompiledModule = new ModuleCtor(filePath, module);
  mod.filename = filePath;
  mod.paths = ModuleCtor._nodeModulePaths(path.dirname(filePath));
  mod._compile(js, filePath);
  return mod.exports;
}

function isPlugin(value: unknown): value is Plugin {
  return (
    typeof value === 'object' &&
    value !== null &&
    typeof (value as { name?: unknown }).name === 'string'
  );
}

function isPluginClass(value: unknown): value is new () => Plugin {
  return typeof value === 'function';
}

function normalizePlugin(candidate: unknown): Plugin | undefined {
  if (isPlugin(candidate)) {
    return candidate;
  }
  if (isPluginClass(candidate)) {
    return new candidate();
  }
  return undefined;
}

function resolvePluginModulePath(entry: string, rootDir: string): string {
  const pluginsDir = path.join(rootDir, 'plugins');
  const base = path.isAbsolute(entry) ? entry : path.join(rootDir, entry);
  const candidates = [base, `${base}.ts`, path.join(pluginsDir, entry), `${path.join(pluginsDir, entry)}.ts`];
  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }
  throw new Error(`Plugin module not found: ${entry}`);
}

function resolvePluginEntry(entry: PluginModule, rootDir: string): Plugin | undefined {
  if (typeof entry === 'string') {
    const modPath = resolvePluginModulePath(entry, rootDir);
    const exports = loadTsModule(modPath) as { default?: unknown; plugin?: unknown };
    return normalizePlugin(exports.default ?? exports.plugin ?? exports);
  }
  return normalizePlugin(entry);
}

export function loadConfiguredPlugins(rootDir: string = process.cwd()): Plugin[] {
  const configPath = path.join(rootDir, 'ssg.config.ts');
  if (!fs.existsSync(configPath)) {
    return [];
  }

  let config: SSGConfig;
  try {
    const exports = loadTsModule(configPath) as { default?: SSGConfig };
    config = (exports.default ?? exports) as SSGConfig;
  } catch (err) {
    console.warn(`Failed to load ${configPath}: ${(err as Error).message}`);
    return [];
  }

  const plugins: Plugin[] = [];
  for (const entry of config.plugins ?? []) {
    try {
      const plugin = resolvePluginEntry(entry, rootDir);
      if (plugin) {
        plugins.push(plugin);
      }
    } catch (err) {
      console.warn(`Failed to load plugin ${String(entry)}: ${(err as Error).message}`);
    }
  }
  return plugins;
}
