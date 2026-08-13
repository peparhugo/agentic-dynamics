import { promises as fs } from 'node:fs';
import path from 'node:path';
import ts from 'typescript';
import type { BuildOptions, SsgConfig } from './plugin';

function loadTypeScriptModule(file: string): SsgConfig {
  const extension = require.extensions['.ts'];
  require.extensions['.ts'] = (module, filename) => {
    const source = require('node:fs').readFileSync(filename, 'utf8') as string;
    const output = ts.transpileModule(source, {
      compilerOptions: {
        esModuleInterop: true,
        module: ts.ModuleKind.CommonJS,
        target: ts.ScriptTarget.ES2022
      },
      fileName: filename
    }).outputText;
    (module as NodeJS.Module & { _compile(source: string, filename: string): void })._compile(output, filename);
  };

  try {
    const loaded = require(file) as { default?: SsgConfig } & SsgConfig;
    return loaded.default ?? loaded;
  } finally {
    if (extension) require.extensions['.ts'] = extension;
    else delete require.extensions['.ts'];
  }
}

async function exists(file: string): Promise<boolean> {
  try {
    await fs.access(file);
    return true;
  } catch {
    return false;
  }
}

export async function resolveConfig(options: BuildOptions): Promise<{ config: SsgConfig; baseDir: string }> {
  const requested = options.configFile
    ? path.resolve(options.configFile)
    : path.resolve('ssg.config.ts');
  if (!await exists(requested)) {
    if (options.configFile) throw new Error(`Config file not found: ${requested}`);
    return { config: {}, baseDir: process.cwd() };
  }

  delete require.cache[requested];
  return { config: loadTypeScriptModule(requested), baseDir: path.dirname(requested) };
}
