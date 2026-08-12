import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import * as ts from 'typescript';
import type { Plugin } from './plugin';

export interface SSGConfig {
  plugins?: Plugin[];
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
  port?: number;
  [key: string]: unknown;
}

export function loadConfig(configPath = 'ssg.config.ts'): SSGConfig | undefined {
  const resolved = path.resolve(configPath);
  if (!existsSync(resolved)) {
    return undefined;
  }
  const loaded = loadTsModule(resolved);
  const candidate = loaded as { default?: SSGConfig };
  return (candidate?.default ?? loaded) as SSGConfig;
}

function loadTsModule(filename: string, seen: Set<string> = new Set()): unknown {
  const resolved = path.resolve(filename);
  if (seen.has(resolved)) {
    return {};
  }
  seen.add(resolved);

  const source = readFileSync(resolved, 'utf8');
  const js = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2020,
      esModuleInterop: true,
    },
    reportDiagnostics: false,
  }).outputText;

  const moduleObject = { exports: {} };
  const baseDir = path.dirname(resolved);
  const localRequire = (id: string): unknown => {
    if (id.startsWith('.') || path.isAbsolute(id)) {
      return resolveTsOrJs(path.join(baseDir, id), localRequire, seen);
    }
    return require(id);
  };

  const fn = new Function('module', 'exports', 'require', '__dirname', '__filename', js);
  fn(moduleObject, moduleObject.exports, localRequire, baseDir, resolved);
  return moduleObject.exports;
}

function resolveTsOrJs(base: string, localRequire: (id: string) => unknown, seen: Set<string>): unknown {
  const candidates = [
    base,
    `${base}.ts`,
    `${base}.tsx`,
    `${base}.js`,
    `${base}.jsx`,
    path.join(base, 'index.ts'),
    path.join(base, 'index.js'),
  ];
  for (const candidate of candidates) {
    if (existsSync(candidate)) {
      if (/\.tsx?$/.test(candidate)) {
        return loadTsModule(candidate, seen);
      }
      return require(candidate);
    }
  }
  throw new Error(`Cannot resolve module: ${base}`);
}
