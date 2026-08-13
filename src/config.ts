import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import ts from 'typescript';
import type { SsgConfig } from './plugin.js';

function loadTypeScriptModule(filePath: string): unknown {
  const previous = require.extensions['.ts'];
  require.extensions['.ts'] = (loaded, filename) => {
    const output = ts.transpileModule(readFileSync(filename, 'utf8'), {
      compilerOptions: {
        esModuleInterop: true,
        module: ts.ModuleKind.CommonJS,
        moduleResolution: ts.ModuleResolutionKind.Node16,
        target: ts.ScriptTarget.ES2022,
      },
      fileName: filename,
    }).outputText;
    (loaded as NodeModule & { _compile(content: string, name: string): void })._compile(output, filename);
  };
  try {
    return require(filePath) as unknown;
  } finally {
    if (previous) require.extensions['.ts'] = previous;
    else delete require.extensions['.ts'];
  }
}

export function loadConfig(configFile = path.resolve('ssg.config.ts')): SsgConfig {
  const resolved = path.resolve(configFile);
  if (!existsSync(resolved)) return {};
  const extension = path.extname(resolved).toLowerCase();
  const loaded = extension === '.ts'
    ? loadTypeScriptModule(resolved)
    : require(resolved) as unknown;
  const moduleValue = loaded as { default?: unknown };
  const config = (moduleValue.default ?? loaded) as SsgConfig;
  if (!config || typeof config !== 'object') throw new Error(`Invalid SSG config: ${resolved}`);
  if (config.plugins !== undefined && !Array.isArray(config.plugins)) {
    throw new Error(`Invalid plugins in SSG config: ${resolved}`);
  }
  return config;
}
