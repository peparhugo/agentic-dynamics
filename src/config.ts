import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import ts from 'typescript';
import { Plugin } from './plugin';

interface SsgConfig {
  plugins?: Plugin[];
}

interface CompilableModule {
  _compile(content: string, filename: string): void;
}

function enableTypeScriptModules(): void {
  if (require.extensions['.ts']) return;
  require.extensions['.ts'] = (module, filename: string) => {
    const source = readFileSync(filename, 'utf8');
    const output = ts.transpileModule(source, {
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true },
      fileName: filename,
    });
    (module as unknown as CompilableModule)._compile(output.outputText, filename);
  };
}

export function loadConfiguredPlugins(configPath = resolve('ssg.config.ts')): Plugin[] {
  if (!existsSync(configPath)) return [];
  enableTypeScriptModules();
  const config = require(configPath) as SsgConfig | { default: SsgConfig };
  const value = 'default' in config ? config.default : config;
  if (!value.plugins) return [];
  if (!Array.isArray(value.plugins)) throw new Error('ssg.config.ts plugins must be an array');
  return value.plugins;
}
