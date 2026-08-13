import { existsSync, readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import type { BuildOptions } from './site';
import type { Plugin } from './plugins/plugin';

export interface SsgConfig extends BuildOptions {
  plugins?: Plugin[];
}

function loadTypeScriptModule(path: string): unknown {
  // Config files and local plugins are TypeScript even when the CLI runs from dist.
  const typescript = require('typescript') as typeof import('typescript');
  const previousLoader = require.extensions['.ts'];
  require.extensions['.ts'] = (module: NodeModule, filename: string): void => {
    const compiled = typescript.transpileModule(readFileSync(filename, 'utf8'), {
      compilerOptions: { module: typescript.ModuleKind.CommonJS, target: typescript.ScriptTarget.ES2021, esModuleInterop: true },
      fileName: filename
    }).outputText;
    (module as unknown as { _compile(source: string, file: string): void })._compile(compiled, filename);
  };
  const source = typescript.transpileModule(readFileSync(path, 'utf8'), {
    compilerOptions: { module: typescript.ModuleKind.CommonJS, target: typescript.ScriptTarget.ES2021, esModuleInterop: true },
    fileName: path
  }).outputText;
  const module = { exports: {} as unknown };
  const localRequire = require('module').createRequire(path) as NodeRequire;
  try {
    new Function('exports', 'require', 'module', '__filename', '__dirname', source)(module.exports, localRequire, module, path, dirname(path));
    return module.exports;
  } finally {
    if (previousLoader) require.extensions['.ts'] = previousLoader;
    else delete require.extensions['.ts'];
  }
}

export function loadConfig(configPath = resolve('ssg.config.ts')): SsgConfig {
  if (!existsSync(configPath)) return {};
  const loaded = loadTypeScriptModule(configPath) as { default?: SsgConfig } | SsgConfig;
  return (loaded && typeof loaded === 'object' && 'default' in loaded ? loaded.default : loaded) ?? {};
}
