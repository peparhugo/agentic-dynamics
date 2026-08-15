import fs from 'fs';
import path from 'path';
import ts from 'typescript';
import type { Plugin, PluginFactory, SSGConfig } from './plugins/types';

type LoadedModule = { default?: unknown } | unknown;
type RequireExtensions = Record<string, (module: unknown, filename: string) => void>;
type TsModule = { _compile(code: string, filename: string): void };

/**
 * Register a CommonJS loader for `.ts` files so plugin modules and the
 * `ssg.config.ts` file can be `require`d at runtime without a build step.
 * Existing loaders (e.g. ts-jest) are left untouched.
 */
function registerTypeScriptLoader(): void {
  const extensions = (require as unknown as { extensions: RequireExtensions }).extensions;
  if (extensions['.ts']) {
    return;
  }
  extensions['.ts'] = (module, filename) => {
    const source = fs.readFileSync(filename, 'utf8');
    const { outputText } = ts.transpileModule(source, {
      fileName: filename,
      compilerOptions: {
        module: ts.ModuleKind.CommonJS,
        target: ts.ScriptTarget.ES2020,
        esModuleInterop: true,
      },
    });
    (module as TsModule)._compile(outputText, filename);
  };
}

function loadModule(filePath: string): unknown {
  registerTypeScriptLoader();
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  const loaded = require(filePath) as LoadedModule;
  const value = (loaded as { default?: unknown }).default ?? loaded;
  return value;
}

function fileCandidates(base: string): string[] {
  if (path.extname(base)) {
    return [base];
  }
  return [base, `${base}.ts`, `${base}.js`];
}

function findFile(candidates: string[]): string | null {
  return (
    candidates.find((candidate) => fs.existsSync(candidate) && fs.statSync(candidate).isFile()) ??
    null
  );
}

/**
 * Resolve the `ssg.config.ts` file. Uses `./ssg.config.ts` relative to
 * `rootDir` (the current working directory by default).
 */
export function loadConfig(configPath?: string, rootDir: string = process.cwd()): SSGConfig | null {
  const given = configPath ?? path.resolve(rootDir, 'ssg.config.ts');
  const resolved = findFile(fileCandidates(given));
  if (!resolved) {
    return null;
  }
  const value = loadModule(resolved);
  return value && typeof value === 'object' ? (value as SSGConfig) : null;
}

/**
 * Resolve a plugin entry. Strings are module names under `./plugins/`
 * (or explicit paths); the returned value is a `Plugin` instance or a
 * `PluginFactory` when the module exports a factory function.
 */
export function loadPluginModule(entry: string, rootDir: string = process.cwd()): Plugin | PluginFactory {
  let resolved: string;
  if (path.isAbsolute(entry)) {
    resolved = entry;
  } else if (entry.startsWith('.')) {
    resolved = path.resolve(rootDir, entry);
  } else {
    resolved = path.resolve(rootDir, 'plugins', entry);
  }
  const existing = findFile([
    resolved,
    ...fileCandidates(resolved),
    ...fileCandidates(path.join(resolved, 'index')),
  ]);
  if (!existing) {
    throw new Error(`Plugin module not found: ${entry}`);
  }
  const value = loadModule(existing);
  if (typeof value === 'function') {
    return value as PluginFactory;
  }
  return value as Plugin;
}

/**
 * Build the plugin list declared in a config file. String entries are loaded
 * from `./plugins/`; inline plugin instances and factories pass through.
 */
export function pluginsFromConfig(
  config: SSGConfig | null,
  rootDir: string = process.cwd()
): Array<Plugin | PluginFactory> {
  if (!config || !Array.isArray(config.plugins)) {
    return [];
  }
  return config.plugins.map((entry) => {
    if (typeof entry === 'string') {
      return loadPluginModule(entry, rootDir);
    }
    return entry;
  });
}
