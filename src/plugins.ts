import { existsSync } from 'node:fs';
import { resolve } from 'node:path';
import { BuildContext, Plugin } from './types';

export interface SsgConfig {
  plugins?: Plugin[];
}

/** Loads the optional project configuration without making it a runtime dependency. */
export function loadConfiguredPlugins(directory = process.cwd()): Plugin[] {
  const configPath = resolve(directory, 'ssg.config.ts');
  if (!existsSync(configPath)) return [];

  // Configurations are TypeScript modules, so compile just this module at load time.
  const TypeScript = require('typescript') as typeof import('typescript');
  const extensions = require.extensions as Record<string, unknown>;
  const original = extensions['.ts'];
  extensions['.ts'] = (module: { _compile(content: string, fileName: string): void }, filename: string): void => {
    const source = require('node:fs').readFileSync(filename, 'utf8') as string;
    const output = TypeScript.transpileModule(source, {
      compilerOptions: { module: TypeScript.ModuleKind.CommonJS, target: TypeScript.ScriptTarget.ES2022, esModuleInterop: true },
      fileName: filename,
    }).outputText;
    (module as unknown as { _compile(content: string, fileName: string): void })._compile(output, filename);
  };
  try {
    delete require.cache[configPath];
    const loaded = require(configPath) as { default?: SsgConfig } & SsgConfig;
    const config = loaded.default ?? loaded;
    if (config.plugins !== undefined && !Array.isArray(config.plugins)) throw new Error('ssg.config.ts plugins must be an array');
    return config.plugins ?? [];
  } finally {
    if (original) extensions['.ts'] = original;
    else delete extensions['.ts'];
  }
}

export async function runHook(context: BuildContext, plugins: Plugin[], hook: 'onStart' | 'beforeBuild' | 'afterBuild' | 'onEnd'): Promise<void> {
  for (const plugin of plugins) await plugin[hook]?.(context);
}
