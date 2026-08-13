import path from 'node:path';
import { promises as fs } from 'node:fs';
import ts from 'typescript';
import type { BuildOptions, Page } from './types';

export interface PluginContext {
  readonly options: Required<Pick<BuildOptions, 'content' | 'output' | 'templates'>> & BuildOptions;
  readonly pages: Page[];
  build(): Promise<Page[]>;
}

export interface Plugin {
  name?: string;
  onStart?(context: PluginContext): void | Promise<void>;
  beforeBuild?(context: PluginContext): void | Promise<void>;
  afterBuild?(context: PluginContext): void | Promise<void>;
  onFile?(page: Page, context: PluginContext): void | Promise<void>;
  onEnd?(context: PluginContext): void | Promise<void>;
}

export interface SsgConfig {
  plugins?: Plugin[];
}

function loadTypeScriptModule(file: string): unknown {
  const extensions = require.extensions as NodeJS.RequireExtensions;
  const previous = extensions['.ts'];
  extensions['.ts'] = (module, filename) => {
    const source = require('node:fs').readFileSync(filename, 'utf8') as string;
    const output = ts.transpileModule(source, {
      compilerOptions: {
        esModuleInterop: true,
        module: ts.ModuleKind.CommonJS,
        moduleResolution: ts.ModuleResolutionKind.Node10,
        target: ts.ScriptTarget.ES2022,
      },
      fileName: filename,
    }).outputText;
    (module as NodeJS.Module & { _compile(source: string, filename: string): void })._compile(output, filename);
  };
  try {
    const configRoot = path.dirname(file);
    const clearLocalModule = (module: NodeJS.Module | undefined): void => {
      if (!module) return;
      for (const child of module.children) {
        if (child.filename.startsWith(`${configRoot}${path.sep}`)) clearLocalModule(child);
      }
      delete require.cache[module.filename];
    };
    const resolved = require.resolve(file);
    clearLocalModule(require.cache[resolved]);
    return require(file) as unknown;
  } finally {
    if (previous) extensions['.ts'] = previous;
    else delete extensions['.ts'];
  }
}

export async function loadPlugins(options: BuildOptions): Promise<Plugin[]> {
  if (options.config === false) return options.plugins ?? [];
  const configFile = path.resolve(typeof options.config === 'string' ? options.config : 'ssg.config.ts');
  try {
    if (!(await fs.stat(configFile)).isFile()) return options.plugins ?? [];
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT' && options.config === undefined) {
      return options.plugins ?? [];
    }
    throw error;
  }

  const loaded = loadTypeScriptModule(configFile);
  if (!loaded || typeof loaded !== 'object') throw new Error(`Invalid SSG config: ${configFile}`);
  const module = loaded as { default?: unknown };
  const config = ('default' in module ? module.default : module) as SsgConfig | undefined;
  if (!config || typeof config !== 'object' || (config.plugins !== undefined && !Array.isArray(config.plugins))) {
    throw new Error(`Invalid SSG config: ${configFile}`);
  }
  return [...(config.plugins ?? []), ...(options.plugins ?? [])];
}
