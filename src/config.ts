import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import ts from 'typescript';
import type { BuildOptions, Plugin, SsgConfig } from './types';

type ConfigPlugin = Plugin | string;

function loadTypeScriptModule(modulePath: string): unknown {
  const previous = require.extensions['.ts'];
  require.extensions['.ts'] = (module, filename) => {
    const source = readFileSync(filename, 'utf8');
    const output = ts.transpileModule(source, {
      compilerOptions: {
        target: ts.ScriptTarget.ES2022,
        module: ts.ModuleKind.CommonJS,
        moduleResolution: ts.ModuleResolutionKind.Node10,
        esModuleInterop: true,
      },
      fileName: filename,
    });
    (module as NodeModule & { _compile(source: string, filename: string): void })._compile(output.outputText, filename);
  };
  try {
    delete require.cache[require.resolve(modulePath)];
    return require(modulePath) as unknown;
  } finally {
    if (previous) require.extensions['.ts'] = previous;
    else delete require.extensions['.ts'];
  }
}

function moduleValue(value: unknown): unknown {
  if (value && typeof value === 'object' && 'default' in value) {
    return (value as { default: unknown }).default;
  }
  return value;
}

function isPlugin(value: unknown): value is Plugin {
  if (!value || typeof value !== 'object') return false;
  return ['onStart', 'beforeBuild', 'afterBuild', 'onFile', 'onEnd']
    .some((hook) => typeof (value as Record<string, unknown>)[hook] === 'function');
}

function resolvePlugin(entry: ConfigPlugin, configDirectory: string): Plugin {
  let value: unknown = entry;
  if (typeof value === 'string') {
    let modulePath = path.resolve(configDirectory, value);
    if (!path.extname(modulePath) && existsSync(`${modulePath}.ts`)) modulePath += '.ts';
    modulePath = require.resolve(modulePath);
    value = moduleValue(loadTypeScriptModule(modulePath));
  }
  if (typeof value === 'function') {
    const candidate = value as Function & { prototype?: Record<string, unknown> };
    const hasHooks = candidate.prototype && ['onStart', 'beforeBuild', 'afterBuild', 'onFile', 'onEnd']
      .some((hook) => typeof candidate.prototype?.[hook] === 'function');
    value = hasHooks ? new (value as new () => unknown)() : (value as () => unknown)();
  }
  if (!isPlugin(value)) throw new Error('Configured plugin must implement at least one lifecycle hook');
  return value;
}

export function loadConfiguredPlugins(options: BuildOptions): Plugin[] {
  const configured = [...(options.plugins ?? [])];
  const requestedPath = options.configFile ? path.resolve(options.configFile) : path.resolve('ssg.config.ts');
  if (!existsSync(requestedPath)) {
    if (options.configFile) throw new Error(`Config file not found: ${requestedPath}`);
    return configured;
  }

  const loaded = moduleValue(loadTypeScriptModule(requestedPath));
  const config = (typeof loaded === 'function' ? loaded() : loaded) as SsgConfig | undefined;
  if (!config || typeof config !== 'object') throw new Error('SSG config must export an object');
  const entries = (config.plugins ?? []) as ConfigPlugin[];
  return [...entries.map((entry) => resolvePlugin(entry, path.dirname(requestedPath))), ...configured];
}
