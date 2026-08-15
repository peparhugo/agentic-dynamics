import fs from 'fs';
import path from 'path';
import type { Plugin } from './plugin';
import type { BuildOptions } from './types';
import { MarkdownPlugin } from './plugins/markdown';
import { TemplatePlugin } from './plugins/template';
import { DevServerPlugin } from './plugins/dev-server';

export interface SsgConfig {
  plugins?: Plugin[];
}

const CONFIG_FILENAMES = ['ssg.config.ts', 'ssg.config.js', 'ssg.config.json'];

/**
 * The set of built-in plugins that ship with the SSG. They are always loaded
 * first so that core behavior (Markdown parsing, template rendering, and the
 * dev server) is available regardless of the user's config.
 */
export function createBuiltInPlugins(): Plugin[] {
  return [new MarkdownPlugin(), new TemplatePlugin(), new DevServerPlugin()];
}

/**
 * Resolve the plugins to use for a build: the built-in plugins followed by any
 * plugins supplied directly on the options or declared in `ssg.config.ts`.
 */
export function loadPlugins(options: BuildOptions): Plugin[] {
  const plugins = createBuiltInPlugins();

  if (options.plugins && options.plugins.length > 0) {
    plugins.push(...options.plugins);
    return plugins;
  }

  const configPath = options.config ?? findConfigPath();
  if (!configPath) return plugins;

  const config = loadConfigFile(configPath);
  if (config && config.plugins) {
    plugins.push(...config.plugins);
  }

  return plugins;
}

function findConfigPath(): string | undefined {
  const cwd = process.cwd();
  for (const filename of CONFIG_FILENAMES) {
    const candidate = path.join(cwd, filename);
    if (fs.existsSync(candidate)) return candidate;
  }
  return undefined;
}

function loadConfigFile(configPath: string): SsgConfig {
  const ext = path.extname(configPath).toLowerCase();

  if (ext === '.json') {
    return normalizeConfig(JSON.parse(fs.readFileSync(configPath, 'utf-8')));
  }

  if (ext === '.js') {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    return normalizeConfig(require(configPath));
  }

  return loadTypeScriptConfig(configPath);
}

function loadTypeScriptConfig(configPath: string): SsgConfig {
  const source = fs.readFileSync(configPath, 'utf-8');
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  const ts = require('typescript') as typeof import('typescript');
  const transpiled = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2020,
      esModuleInterop: true,
    },
  }).outputText;

  // eslint-disable-next-line @typescript-eslint/no-var-requires
  const Module: any = require('module');
  const mod = new Module(configPath, module);
  mod.filename = configPath;
  mod.paths = Module._nodeModulePaths(path.dirname(configPath));
  mod._compile(transpiled, configPath);

  const exported = mod.exports;
  if (exported && typeof exported === 'object' && 'default' in exported) {
    return normalizeConfig(exported.default);
  }
  return normalizeConfig(exported);
}

function normalizeConfig(config: unknown): SsgConfig {
  if (config && typeof config === 'object' && 'plugins' in config) {
    return config as SsgConfig;
  }
  return {};
}
