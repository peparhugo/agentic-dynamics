import { existsSync } from 'node:fs';
import path from 'node:path';

export interface PluginPage {
  sourcePath: string;
  relativePath: string;
  outputPath: string;
  url: string;
  source: string;
  data: Record<string, unknown>;
  title: string;
  date?: string;
  tags: string[];
  content: string;
  html: string;
}

export interface PluginContext {
  contentDir: string;
  outputDir: string;
  templatesDir: string;
  pages: PluginPage[];
}

export interface Plugin {
  name?: string;
  onStart?(context: PluginContext): void | Promise<void>;
  beforeBuild?(context: PluginContext): void | Promise<void>;
  afterBuild?(context: PluginContext): void | Promise<void>;
  onFile?(page: PluginPage): void | Promise<void>;
  onEnd?(context: PluginContext): void | Promise<void>;
}

export interface SsgConfig {
  plugins?: Plugin[];
}

export function defineConfig(config: SsgConfig): SsgConfig {
  return config;
}

function isPlugin(value: unknown): value is Plugin {
  return typeof value === 'object' && value !== null;
}

/** Load a TypeScript config and its local TypeScript plugin modules. */
export function loadPlugins(configFile = './ssg.config.ts'): Plugin[] {
  const resolved = path.resolve(configFile);
  if (!existsSync(resolved)) return [];

  // Config files are user-owned TypeScript and are not part of this package's build.
  // Transpile them on demand so the documented .ts format works on every supported Node version.
  const typescript = require('typescript') as typeof import('typescript');
  const extensions = require.extensions as NodeJS.RequireExtensions;
  const previousLoader = extensions['.ts'];
  extensions['.ts'] = (module, filename) => {
    const source = require('node:fs').readFileSync(filename, 'utf8') as string;
    const output = typescript.transpileModule(source, {
      compilerOptions: {
        esModuleInterop: true,
        module: typescript.ModuleKind.CommonJS,
        target: typescript.ScriptTarget.ES2022,
      },
      fileName: filename,
    }).outputText;
    (module as NodeJS.Module & { _compile(source: string, filename: string): void })._compile(output, filename);
  };

  try {
    delete require.cache[resolved];
    const loaded = require(resolved) as { default?: SsgConfig } & SsgConfig;
    const config = loaded.default ?? loaded;
    if (!config || (config.plugins !== undefined && !Array.isArray(config.plugins))) {
      throw new Error(`Invalid SSG config: ${resolved}`);
    }
    const plugins = config.plugins ?? [];
    if (!plugins.every(isPlugin)) throw new Error(`Invalid plugin in SSG config: ${resolved}`);
    return plugins;
  } finally {
    if (previousLoader) extensions['.ts'] = previousLoader;
    else delete extensions['.ts'];
  }
}

export class PluginPipeline {
  constructor(private readonly plugins: Plugin[]) {}

  async run(hook: 'onStart' | 'beforeBuild' | 'afterBuild' | 'onEnd', context: PluginContext): Promise<void> {
    for (const plugin of this.plugins) await plugin[hook]?.(context);
  }

  async onFile(page: PluginPage): Promise<void> {
    for (const plugin of this.plugins) await plugin.onFile?.(page);
  }
}
