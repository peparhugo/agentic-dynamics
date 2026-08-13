import { promises as fs } from 'node:fs';
import path from 'node:path';
import type { Plugin, SsgConfig } from './types';

const isPlugin = (value: unknown): value is Plugin => typeof value === 'object' && value !== null;

export async function loadPlugins(configFile = path.resolve('ssg.config.ts')): Promise<Plugin[]> {
  const exists = await fs.stat(configFile).then((stats) => stats.isFile()).catch(() => false);
  if (!exists) return [];

  const extension = path.extname(configFile).toLowerCase();
  let restore: (() => void) | undefined;
  if (extension === '.ts') {
    // Config and local plugin modules are transpiled on demand without changing global registration permanently.
    const typescript = require('typescript') as typeof import('typescript');
    const previous = require.extensions['.ts'];
    require.extensions['.ts'] = (module, filename) => {
      const source = require('node:fs').readFileSync(filename, 'utf8') as string;
      const output = typescript.transpileModule(source, {
        compilerOptions: { module: typescript.ModuleKind.CommonJS, target: typescript.ScriptTarget.ES2022, esModuleInterop: true },
        fileName: filename,
      }).outputText;
      (module as NodeModule & { _compile(source: string, filename: string): void })._compile(output, filename);
    };
    restore = () => {
      if (previous) require.extensions['.ts'] = previous;
      else delete require.extensions['.ts'];
    };
  }

  try {
    delete require.cache[require.resolve(configFile)];
    const loaded = require(configFile) as SsgConfig & { default?: SsgConfig };
    const config = loaded.default ?? loaded;
    const plugins = config.plugins ?? [];
    if (!Array.isArray(plugins) || !plugins.every(isPlugin)) throw new Error(`Invalid plugins in config: ${configFile}`);
    return plugins;
  } finally {
    restore?.();
  }
}
