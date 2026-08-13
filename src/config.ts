import * as fs from 'fs';
import * as ts from 'typescript';
import { Plugin } from './plugin';

export interface SSGConfig {
  plugins: Plugin[];
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
}

let tsRequireHookRegistered = false;

/**
 * Registers a `require.extensions['.ts']` handler that transpiles
 * TypeScript to CommonJS on the fly via the TypeScript compiler API, so
 * plain `require()` can load `ssg.config.ts` (and any `.ts` plugin modules
 * it imports) without a build step. Under Jest, ts-jest already transforms
 * `.ts` requires before Node's `require.extensions` is consulted, so this
 * hook is inert there.
 */
function registerTsRequireHook(): void {
  if (tsRequireHookRegistered || require.extensions['.ts']) {
    tsRequireHookRegistered = true;
    return;
  }
  tsRequireHookRegistered = true;

  require.extensions['.ts'] = (mod: NodeJS.Module, filename: string) => {
    const source = fs.readFileSync(filename, 'utf-8');
    const { outputText } = ts.transpileModule(source, {
      compilerOptions: {
        module: ts.ModuleKind.CommonJS,
        target: ts.ScriptTarget.ES2020,
        esModuleInterop: true,
      },
      fileName: filename,
    });
    (mod as unknown as { _compile(code: string, filename: string): void })._compile(outputText, filename);
  };
}

/**
 * Loads plugin configuration from `configPath` (an `ssg.config.ts` or
 * `.js` module exporting an `SSGConfig`, either as `export default` or
 * CommonJS `module.exports`). Returns `{ plugins: [] }` when the file
 * doesn't exist, so callers can fall back to a default plugin set.
 */
export function loadConfig(configPath: string): SSGConfig {
  if (!fs.existsSync(configPath)) {
    return { plugins: [] };
  }

  registerTsRequireHook();
  delete require.cache[require.resolve(configPath)];
  const loaded = require(configPath);
  const config = (loaded?.default ?? loaded) as Partial<SSGConfig>;

  return {
    plugins: Array.isArray(config.plugins) ? config.plugins : [],
    contentDir: config.contentDir,
    outputDir: config.outputDir,
    templatesDir: config.templatesDir,
  };
}
