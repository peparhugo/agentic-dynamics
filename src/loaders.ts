import path from 'path';
import { promises as fs, existsSync, readFileSync } from 'fs';
import Module from 'module';
import { pathToFileURL } from 'url';

type ResolveFilename = (
  request: string,
  parent: NodeModule | null,
  isMain: boolean,
  options?: Record<string, unknown>
) => string;

const ModuleWithInternals = Module as unknown as {
  _resolveFilename: ResolveFilename;
};

const requireExtensions = (require as { extensions?: Record<string, unknown> })
  .extensions ?? {};

let typescript: typeof import('typescript') | null | undefined;

function getTypescript(): typeof import('typescript') | undefined {
  if (typescript === undefined) {
    try {
      // eslint-disable-next-line @typescript-eslint/no-var-requires
      typescript = require('typescript') as typeof import('typescript');
    } catch {
      typescript = null;
    }
  }
  return typescript ?? undefined;
}

let tsHookInstalled = false;

function ensureTsRequireHook(): void {
  if (tsHookInstalled) {
    return;
  }
  tsHookInstalled = true;

  const originalResolve = ModuleWithInternals._resolveFilename;

  const resolveCandidates = (
    request: string,
    parent?: NodeModule | null
  ): string | null => {
    if (!request.startsWith('.') && !path.isAbsolute(request)) {
      return null;
    }
    const base = parent ? path.dirname(parent.filename) : process.cwd();
    const abs = path.resolve(base, request);
    const candidates = [
      abs,
      `${abs}.ts`,
      `${abs}.tsx`,
      `${abs}.mts`,
      `${abs}.js`,
      `${abs}.cjs`,
      `${abs}.json`,
      path.join(abs, 'index.ts'),
      path.join(abs, 'index.js'),
      path.join(abs, 'index.json'),
    ];
    for (const candidate of candidates) {
      if (existsSync(candidate)) {
        return candidate;
      }
    }
    return null;
  };

  ModuleWithInternals._resolveFilename = function (request, parent, isMain, options) {
    const resolved = resolveCandidates(request, parent);
    if (resolved) {
      return resolved;
    }
    return originalResolve.call(this, request, parent, isMain, options);
  };

  const compile = (module: NodeModule, filename: string): void => {
    const ts = getTypescript();
    if (!ts) {
      throw new Error(
        'Loading a TypeScript config or plugin requires the "typescript" package to be installed.'
      );
    }
    const source = readFileSync(filename, 'utf8');
    const result = ts.transpileModule(source, {
      compilerOptions: {
        module: ts.ModuleKind.CommonJS,
        target: ts.ScriptTarget.ES2020,
        esModuleInterop: true,
        allowSyntheticDefaultImports: true,
        moduleResolution: ts.ModuleResolutionKind.NodeJs,
        skipLibCheck: true,
      },
      fileName: filename,
    });
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (module as any)._compile(result.outputText, filename);
  };

  requireExtensions['.ts'] = compile as unknown;
  requireExtensions['.tsx'] = compile as unknown;
  requireExtensions['.mts'] = compile as unknown;
}

export async function loadModule(filePath: string): Promise<unknown> {
  const ext = path.extname(filePath).toLowerCase();
  if (ext === '.mjs') {
    const mod = await import(pathToFileURL(filePath).href);
    return (mod as { default?: unknown }).default ?? mod;
  }
  if (ext === '.ts' || ext === '.tsx' || ext === '.mts') {
    ensureTsRequireHook();
  }
  if (ext === '.json') {
    return JSON.parse(await fs.readFile(filePath, 'utf8'));
  }
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  return require(filePath);
}
