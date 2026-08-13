import { existsSync, promises as fs } from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import ts from 'typescript';
import type { Plugin } from './plugin.js';

interface SsgConfig {
  plugins?: Plugin[];
}

function pluginsFrom(config: SsgConfig | Plugin[] | undefined): Plugin[] {
  return Array.isArray(config) ? config : config?.plugins ?? [];
}

export async function loadPlugins(directory = process.cwd()): Promise<Plugin[]> {
  const jsConfig = path.join(directory, 'ssg.config.js');
  if (existsSync(jsConfig)) return pluginsFrom((await import(pathToFileURL(jsConfig).href)).default as SsgConfig | Plugin[]);

  const tsConfig = path.join(directory, 'ssg.config.ts');
  if (!existsSync(tsConfig)) return [];
  const source = await fs.readFile(tsConfig, 'utf8');
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText;
  // A data URL lets a TypeScript config with inline plugin definitions run without a runtime loader.
  const config = await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`) as { default: SsgConfig };
  return pluginsFrom(config.default);
}
