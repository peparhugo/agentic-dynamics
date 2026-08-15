import * as fs from 'fs';
import * as path from 'path';
import ts from 'typescript';

/**
 * Load a TypeScript module by transpiling it to CommonJS in memory and
 * evaluating it. Returns the module's default export (or the module itself
 * when there is no default export).
 *
 * This is used to load `ssg.config.ts` and plugin modules from `./plugins/`
 * without requiring a registered transpiler hook.
 */
export function loadTsModule<T>(filePath: string): T {
  const source = fs.readFileSync(filePath, 'utf8');
  const compiled = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2020,
      esModuleInterop: true,
    },
    fileName: filePath,
  }).outputText;

  const moduleObj: { exports: Record<string, unknown> } = { exports: {} };
  const dir = path.dirname(filePath);
  const baseRequire = require as (id: string) => unknown;

  const localRequire = (id: string): unknown => {
    if (id.startsWith('.') || id.startsWith('/')) {
      return loadTsModule(path.resolve(dir, id));
    }
    try {
      return baseRequire(id);
    } catch (err) {
      try {
        return baseRequire(require.resolve(id, { paths: [dir] }));
      } catch {
        throw err;
      }
    }
  };

  const factory = new Function(
    'module',
    'exports',
    'require',
    '__filename',
    '__dirname',
    compiled
  );
  factory(moduleObj, moduleObj.exports, localRequire, filePath, dir);

  const loaded = moduleObj.exports.default ?? moduleObj.exports;
  return loaded as T;
}
