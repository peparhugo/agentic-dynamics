import fs from 'fs';
import path from 'path';

import { Plugin } from './plugin';

/**
 * The shape of a `ssg.config.ts` file. It may export the config directly, as a
 * `default` export, or as a function returning the config.
 */
export interface SsgConfig {
  plugins?: Plugin[];
}

const CONFIG_FILENAMES = ['ssg.config.ts', 'ssg.config.js', 'ssg.config.mjs', 'ssg.config.cjs'];

let tsHookInstalled = false;

function compileTypeScript(source: string): string {
  const ts = require('typescript');
  return ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2020,
      esModuleInterop: true,
      moduleResolution: ts.ModuleResolutionKind.NodeJs,
    },
  }).outputText;
}

/**
 * Registers a `require` extension for `.ts` files so that `ssg.config.ts` and
 * its plugin modules (which live in `./plugins/*.ts`) can be loaded at runtime.
 * No-op when TypeScript support is already registered (ts-node, ts-jest, ...).
 */
export function installTypeScriptRequireHook(): void {
  if (tsHookInstalled) {
    return;
  }
  tsHookInstalled = true;

  const extensions = (require as unknown as {
    extensions: Record<string, (mod: NodeModule & { _compile: (code: string, filename: string) => void }, filename: string) => void>;
  }).extensions;

  if (typeof extensions['.ts'] === 'function') {
    return;
  }

  extensions['.ts'] = (mod, filename) => {
    const source = fs.readFileSync(filename, 'utf-8');
    mod._compile(compileTypeScript(source), filename);
  };
}

function findConfigFile(dir: string): string | undefined {
  for (const name of CONFIG_FILENAMES) {
    const candidate = path.join(dir, name);
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }
  return undefined;
}

function unwrapDefault(loaded: unknown): unknown {
  if (loaded && typeof loaded === 'object' && 'default' in (loaded as Record<string, unknown>)) {
    return (loaded as Record<string, unknown>).default;
  }
  return loaded;
}

/**
 * Loads and evaluates a `ssg.config.ts` (or `.js`/`.mjs`/`.cjs`) file from the
 * given directory, returning the exported configuration object.
 */
export function loadConfig(dir: string = process.cwd()): SsgConfig {
  const filePath = findConfigFile(dir);
  if (!filePath) {
    return {};
  }

  installTypeScriptRequireHook();

  const resolved = path.resolve(filePath);
  delete require.cache[resolved];

  let config = unwrapDefault(require(resolved));
  if (typeof config === 'function') {
    config = config();
  }
  if (config == null || typeof config !== 'object') {
    return {};
  }
  return config as SsgConfig;
}

/**
 * Loads the plugin instances declared in the `ssg.config.ts` file located in
 * the given directory.
 */
export function loadPlugins(dir: string = process.cwd()): Plugin[] {
  const config = loadConfig(dir);
  const plugins = config.plugins ?? [];
  return plugins.filter((plugin): plugin is Plugin => !!plugin);
}
