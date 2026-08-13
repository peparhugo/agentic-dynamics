import { promises as fs } from 'node:fs';
import Module from 'node:module';
import path from 'node:path';
import ts from 'typescript';
import { Plugin, SsgConfig } from './plugin';

type ExtensionLoader = (module: NodeModule, filename: string) => void;

async function exists(filePath: string): Promise<boolean> {
  try {
    return (await fs.stat(filePath)).isFile();
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return false;
    throw error;
  }
}

function loadTypeScriptModule(filePath: string): unknown {
  const extensions = (Module as unknown as { _extensions: Record<string, ExtensionLoader> })._extensions;
  const previous = extensions['.ts'];
  extensions['.ts'] = (module, filename) => {
    const source = require('node:fs').readFileSync(filename, 'utf8') as string;
    const javascript = ts.transpileModule(source, {
      compilerOptions: {
        esModuleInterop: true,
        module: ts.ModuleKind.CommonJS,
        target: ts.ScriptTarget.ES2022,
      },
      fileName: filename,
    }).outputText;
    (module as NodeModule & { _compile(source: string, filename: string): void })._compile(javascript, filename);
  };

  try {
    for (const cached of Object.keys(require.cache)) {
      if (cached === filePath || cached.startsWith(`${path.dirname(filePath)}${path.sep}`)) delete require.cache[cached];
    }
    return require(filePath) as unknown;
  } finally {
    if (previous) extensions['.ts'] = previous;
    else delete extensions['.ts'];
  }
}

export async function loadPlugins(configFile: string): Promise<Plugin[]> {
  if (!await exists(configFile)) return [];
  const loaded = path.extname(configFile) === '.ts'
    ? loadTypeScriptModule(configFile)
    : require(configFile) as unknown;
  const exported = loaded as { default?: SsgConfig } & SsgConfig;
  const config = exported.default ?? exported;
  if (!config || (config.plugins !== undefined && !Array.isArray(config.plugins))) {
    throw new Error(`Invalid SSG config: ${configFile}`);
  }
  return config.plugins ?? [];
}
