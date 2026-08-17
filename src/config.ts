import * as fs from 'fs';
import * as path from 'path';
import { Plugin } from './plugin';

export interface SsgConfig {
  plugins?: Plugin[];
}

function compileTs(source: string): string {
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  const ts = require('typescript') as typeof import('typescript');
  return ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2020,
      esModuleInterop: true,
    },
  }).outputText;
}

let tsHookRegistered = false;

function registerTsHook(): void {
  if (tsHookRegistered) {
    return;
  }
  tsHookRegistered = true;

  // eslint-disable-next-line @typescript-eslint/no-var-requires
  const Module: any = require('module');

  require.extensions['.ts'] = function (module: any, filename: string) {
    module._compile(compileTs(fs.readFileSync(filename, 'utf8')), filename);
  };

  const originalResolveFilename = Module._resolveFilename;
  Module._resolveFilename = function (
    request: string,
    parent: any,
    ...rest: unknown[]
  ) {
    if (request.startsWith('./') || request.startsWith('../')) {
      const candidates = [request, `${request}.ts`, `${request}/index.ts`];
      for (const candidate of candidates) {
        try {
          return originalResolveFilename.call(
            this,
            candidate,
            parent,
            ...rest
          );
        } catch {
          // try the next candidate
        }
      }
    }
    return originalResolveFilename.call(this, request, parent, ...rest);
  };
}

export function loadConfig(configPath = 'ssg.config.ts'): SsgConfig {
  const resolved = path.resolve(configPath);
  if (!fs.existsSync(resolved)) {
    return {};
  }

  registerTsHook();

  const source = fs.readFileSync(resolved, 'utf8');
  const js = compileTs(source);

  // eslint-disable-next-line @typescript-eslint/no-var-requires
  const Module: any = require('module');
  const mod = new Module(resolved);
  mod.filename = resolved;
  mod.paths = Module._nodeModulePaths(path.dirname(resolved));
  mod._compile(js, resolved);

  const exported = mod.exports as Record<string, unknown>;
  const config = (exported && 'default' in exported
    ? exported.default
    : exported) as SsgConfig;

  return config ?? {};
}
