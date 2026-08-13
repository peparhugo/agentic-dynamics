import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import ts from 'typescript';
import type { Plugin, SsgConfig } from './plugin.js';

function loadTypeScriptModule(filename: string): unknown {
  const extensions = require.extensions;
  const previous = extensions['.ts'];
  extensions['.ts'] = (module, moduleFilename) => {
    const source = readFileSync(moduleFilename, 'utf8');
    const result = ts.transpileModule(source, {
      compilerOptions: {
        esModuleInterop: true,
        module: ts.ModuleKind.CommonJS,
        moduleResolution: ts.ModuleResolutionKind.Node10,
        target: ts.ScriptTarget.ES2022
      },
      fileName: moduleFilename
    });
    (module as unknown as { _compile(source: string, filename: string): void })._compile(result.outputText, moduleFilename);
  };
  try {
    delete require.cache[filename];
    return require(filename);
  } finally {
    if (previous) extensions['.ts'] = previous;
    else delete extensions['.ts'];
  }
}

function validatePlugins(config: SsgConfig, configPath: string): Plugin[] {
  if (config.plugins === undefined) return [];
  if (!Array.isArray(config.plugins)) {
    throw new Error(`plugins must be an array in ${configPath}`);
  }
  for (const plugin of config.plugins) {
    if (!plugin || typeof plugin !== 'object') {
      throw new Error(`Invalid plugin in ${configPath}`);
    }
  }
  return config.plugins;
}

export function loadPlugins(configFile: string | false | undefined): Plugin[] {
  if (configFile === false) return [];
  const configPath = path.resolve(configFile ?? 'ssg.config.ts');
  if (!existsSync(configPath)) {
    if (configFile) throw new Error(`Config file not found: ${configPath}`);
    return [];
  }
  const loaded = path.extname(configPath) === '.ts'
    ? loadTypeScriptModule(configPath)
    : require(configPath);
  const config = ((loaded as { default?: SsgConfig }).default ?? loaded) as SsgConfig;
  if (!config || typeof config !== 'object') {
    throw new Error(`Invalid SSG config: ${configPath}`);
  }
  return validatePlugins(config, configPath);
}
