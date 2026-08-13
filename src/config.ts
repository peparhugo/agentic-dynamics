import { promises as fs } from 'node:fs';
import path from 'node:path';
import ts from 'typescript';
import { BuildOptions, Plugin, SsgConfig } from './plugin';

async function exists(file: string): Promise<boolean> {
  try {
    return (await fs.stat(file)).isFile();
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return false;
    throw error;
  }
}

function pluginsFrom(value: unknown): Plugin[] {
  const loaded = value as { default?: unknown; plugins?: unknown } | undefined;
  const config = loaded?.default ?? loaded;
  const plugins = Array.isArray(config)
    ? config
    : (config as SsgConfig | undefined)?.plugins ?? loaded?.plugins ?? [];
  if (!Array.isArray(plugins)) throw new Error('ssg.config.ts must export a plugins array');
  return plugins as Plugin[];
}

export async function loadPlugins(options: BuildOptions): Promise<Plugin[]> {
  const configFile = path.resolve(options.configFile ?? './ssg.config.ts');
  if (!(await exists(configFile))) {
    if (options.configFile) throw new Error(`Config not found: ${configFile}`);
    return [];
  }

  const extensions = require.extensions;
  const previous = extensions['.ts'];
  extensions['.ts'] = (module, filename) => {
    const source = require('node:fs').readFileSync(filename, 'utf8') as string;
    const output = ts.transpileModule(source, {
      compilerOptions: { esModuleInterop: true, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
      fileName: filename
    }).outputText;
    (module as NodeModule & { _compile(code: string, file: string): void })._compile(output, filename);
  };
  try {
    delete require.cache[configFile];
    return pluginsFrom(require(configFile));
  } finally {
    if (previous) extensions['.ts'] = previous;
    else delete extensions['.ts'];
  }
}
