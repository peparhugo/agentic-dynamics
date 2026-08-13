import { promises as fs } from 'node:fs';
import path from 'node:path';
import ts from 'typescript';
import type { Plugin, SsgConfig } from './types';

async function isFile(file: string): Promise<boolean> {
  return fs.stat(file).then((stat) => stat.isFile()).catch(() => false);
}

export async function loadPlugins(configFile?: string): Promise<Plugin[]> {
  const file = path.resolve(configFile ?? 'ssg.config.ts');
  if (!await isFile(file)) {
    if (configFile) throw new Error(`Config file not found: ${configFile}`);
    return [];
  }

  const originalLoader = require.extensions['.ts'];
  require.extensions['.ts'] = (module, filename) => {
    const source = require('node:fs').readFileSync(filename, 'utf8') as string;
    const compiled = ts.transpileModule(source, {
      compilerOptions: {
        esModuleInterop: true,
        module: ts.ModuleKind.CommonJS,
        target: ts.ScriptTarget.ES2022,
      },
      fileName: filename,
    }).outputText;
    (module as NodeModule & { _compile(source: string, filename: string): void })._compile(compiled, filename);
  };

  try {
    delete require.cache[require.resolve(file)];
    const loaded = require(file) as { default?: SsgConfig } & SsgConfig;
    const config = loaded.default ?? loaded;
    if (!config || (config.plugins !== undefined && !Array.isArray(config.plugins))) {
      throw new Error(`Invalid config: ${file}`);
    }
    return config.plugins ?? [];
  } finally {
    if (originalLoader) require.extensions['.ts'] = originalLoader;
    else delete require.extensions['.ts'];
  }
}
