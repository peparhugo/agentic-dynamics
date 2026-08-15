import fs from 'fs';
import path from 'path';
import Module from 'module';
import ts from 'typescript';
import { Plugin } from './plugin';
import { MarkdownPlugin } from './plugins/markdown';
import { TemplatePlugin } from './plugins/templates';
import { DevServerPlugin } from './plugins/dev-server';

export interface SsgConfig {
  plugins?: Array<string | Plugin>;
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
  port?: number;
  host?: string;
}

export const CONFIG_FILENAMES = ['ssg.config.ts', 'ssg.config.js', 'ssg.config.json'];

const BUILTIN_PLUGIN_FACTORIES: Record<string, new () => Plugin> = {
  markdown: MarkdownPlugin,
  templates: TemplatePlugin,
  'dev-server': DevServerPlugin,
};

let tsRequireHookInstalled = false;

function installTsRequireHook(): void {
  if (tsRequireHookInstalled) return;
  tsRequireHookInstalled = true;

  const extensions = (Module as unknown as { _extensions: Record<string, unknown> })._extensions;
  const compile: (module: NodeModule, filename: string) => void = (module, filename) => {
    const source = fs.readFileSync(filename, 'utf-8');
    const compiled = ts.transpileModule(source, {
      compilerOptions: {
        module: ts.ModuleKind.CommonJS,
        target: ts.ScriptTarget.ES2020,
        esModuleInterop: true,
      },
    }).outputText;
    (module as unknown as { _compile: (code: string, filename: string) => void })._compile(
      compiled,
      filename
    );
  };
  extensions['.ts'] = compile;
  extensions['.tsx'] = compile;
}

function requireModule(file: string): unknown {
  installTsRequireHook();
  const req = Module.createRequire(file);
  return req(file);
}

function defaultExport(value: unknown): unknown {
  if (value && typeof value === 'object' && 'default' in (value as Record<string, unknown>)) {
    return (value as Record<string, unknown>).default;
  }
  return value;
}

function requireConfig(file: string): unknown {
  if (file.endsWith('.json')) {
    return JSON.parse(fs.readFileSync(file, 'utf-8'));
  }
  return defaultExport(requireModule(file));
}

export function findConfigFile(baseDir: string = process.cwd()): string | null {
  for (const name of CONFIG_FILENAMES) {
    const candidate = path.join(baseDir, name);
    if (fs.existsSync(candidate)) return candidate;
  }
  return null;
}

export function loadConfig(configPath?: string): SsgConfig {
  const file = configPath ?? findConfigFile();
  if (!file) return {};
  const config = requireConfig(file);
  if (config == null) return {};
  if (typeof config !== 'object') {
    throw new Error(`Invalid SSG config: expected an object in ${file}`);
  }
  return config as SsgConfig;
}

function resolvePluginFile(spec: string, baseDir: string): string | null {
  const candidates = [
    path.resolve(baseDir, spec),
    path.resolve(baseDir, 'plugins', spec),
    path.resolve(baseDir, spec, 'index'),
  ];
  const extensions = ['', '.ts', '.js'];
  for (const candidate of candidates) {
    for (const ext of extensions) {
      const file = candidate + ext;
      if (fs.existsSync(file)) return file;
    }
  }
  return null;
}

function instantiatePlugin(value: unknown): Plugin {
  if (typeof value === 'function') {
    return new (value as new () => Plugin)();
  }
  if (value && typeof value === 'object') {
    return value as Plugin;
  }
  throw new Error(`Plugin module must export a Plugin object or constructor`);
}

export function resolvePlugin(spec: string | Plugin, baseDir: string = process.cwd()): Plugin {
  if (typeof spec === 'object' && spec !== null) {
    return spec;
  }
  if (typeof spec !== 'string') {
    throw new Error(`Invalid plugin: ${String(spec)}`);
  }

  const factory = BUILTIN_PLUGIN_FACTORIES[spec];
  if (factory) return new factory();

  const file = resolvePluginFile(spec, baseDir);
  if (!file) {
    throw new Error(`Plugin not found: ${spec}`);
  }
  return instantiatePlugin(defaultExport(requireModule(file)));
}

export function loadPlugins(config?: SsgConfig, baseDir: string = process.cwd()): Plugin[] {
  const specs = config?.plugins ?? [];
  return specs.map((spec) => resolvePlugin(spec, baseDir));
}

export function createConfiguredPlugins(
  config?: SsgConfig,
  baseDir: string = process.cwd()
): Plugin[] {
  const userPlugins = loadPlugins(config, baseDir);
  return [new MarkdownPlugin(), ...userPlugins, new TemplatePlugin()];
}
