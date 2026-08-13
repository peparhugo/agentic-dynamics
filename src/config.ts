import { existsSync } from 'node:fs';
import path from 'node:path';
import ts from 'typescript';
import { BuildOptions, Plugin, SsgConfig } from './types';

type ConfigExport = SsgConfig | Plugin[];

function isPlugin(value: unknown): value is Plugin {
  return typeof value === 'object' && value !== null;
}

function pluginsFrom(value: unknown, filename: string): Plugin[] {
  if (typeof value !== 'object' || value === null) {
    throw new Error(`Invalid config: ${filename}`);
  }
  const config = value as ConfigExport;
  const plugins = Array.isArray(config) ? config : config?.plugins ?? [];
  if (!Array.isArray(plugins) || !plugins.every(isPlugin)) {
    throw new Error(`Invalid plugins in config: ${filename}`);
  }
  return plugins;
}

export function loadPlugins(options: BuildOptions): Plugin[] {
  if (options.plugins) {
    return options.plugins;
  }

  const filename = path.resolve(options.configFile ?? 'ssg.config.ts');
  if (!existsSync(filename)) {
    if (options.configFile) {
      throw new Error(`Config file does not exist: ${filename}`);
    }
    return [];
  }

  const previousLoader = require.extensions['.ts'];
  require.extensions['.ts'] = (module, moduleFilename): void => {
    const source = require('node:fs').readFileSync(moduleFilename, 'utf8') as string;
    const output = ts.transpileModule(source, {
      compilerOptions: {
        esModuleInterop: true,
        module: ts.ModuleKind.CommonJS,
        target: ts.ScriptTarget.ES2022
      },
      fileName: moduleFilename
    }).outputText;
    (module as NodeJS.Module & { _compile(source: string, filename: string): void })
      ._compile(output, moduleFilename);
  };

  try {
    delete require.cache[require.resolve(filename)];
    const loaded = require(filename) as { default?: unknown; plugins?: unknown };
    return pluginsFrom(Object.prototype.hasOwnProperty.call(loaded, 'default') ? loaded.default : loaded, filename);
  } finally {
    if (previousLoader) {
      require.extensions['.ts'] = previousLoader;
    } else {
      delete require.extensions['.ts'];
    }
  }
}
