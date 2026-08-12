import fs from 'node:fs';
import path from 'node:path';
import Module from 'node:module';
import ts from 'typescript';
import { Plugin, PluginContext, PluginFactory } from './plugin';

interface Config { plugins?: PluginFactory[] }

function loadModule(file: string): Config {
  const source = fs.readFileSync(file, 'utf8');
  const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, esModuleInterop: true } }).outputText;
  const previous = require.extensions['.ts'];
  require.extensions['.ts'] = (mod, filename) => {
    const code = ts.transpileModule(fs.readFileSync(filename, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, esModuleInterop: true } }).outputText;
    (mod as Module & { _compile(source: string, filename: string): void })._compile(code, filename);
  };
  const loaded = new Module(file, module);
  loaded.filename = file;
  loaded.paths = Module._nodeModulePaths(path.dirname(file));
  try { (loaded as Module & { _compile(code: string, filename: string): void })._compile(compiled, file); }
  finally { if (previous) require.extensions['.ts'] = previous; else delete require.extensions['.ts']; }
  const exported = loaded.exports.default || loaded.exports;
  return Array.isArray(exported) ? { plugins: exported } : exported as Config;
}

export async function loadConfiguredPlugins(configFile = 'ssg.config.ts', context?: PluginContext, additional: unknown[] = []): Promise<Plugin[]> {
  const file = path.resolve(configFile);
  const config = fs.existsSync(file) ? loadModule(file) : {};
  const result: Plugin[] = [];
  for (const factory of [...(config.plugins || []), ...additional] as PluginFactory[]) result.push(typeof factory === 'function' ? await factory(context as PluginContext) : factory);
  return result;
}
