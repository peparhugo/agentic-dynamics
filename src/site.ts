import { readdir, readFile, rm, mkdir, access } from 'node:fs/promises';
import { join, relative, resolve } from 'node:path';
import { createRequire } from 'node:module';
import ts from 'typescript';
import type { BuildContext, Plugin, SsgConfig } from './plugin';
import { MarkdownPlugin, parsePage } from './plugins/markdown';
import { TemplatePlugin } from './plugins/template';

export interface Page { title: string; date?: string; tags: string[]; slug: string; html: string; template?: string; layout?: string; frontmatter: Record<string, unknown>; }
export interface BuildOptions { contentDir?: string; outputDir?: string; templateDir?: string; configFile?: string; plugins?: Plugin[]; }
export { parsePage };

async function markdownFiles(directory: string): Promise<string[]> {
  try {
    const entries = await readdir(directory, { withFileTypes: true });
    return (await Promise.all(entries.map(async (entry) => entry.isDirectory() ? markdownFiles(join(directory, entry.name)) : entry.isFile() && entry.name.toLowerCase().endsWith('.md') ? [join(directory, entry.name)] : []))).flat();
  } catch (error: unknown) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return [];
    throw error;
  }
}

async function loadConfig(filename: string): Promise<SsgConfig> {
  try {
    await access(filename);
  } catch (error: unknown) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return {};
    throw error;
  }
  const require = createRequire(filename);
  const extensions = require.extensions as Record<string, (module: NodeModule, filename: string) => void>;
  const previous = extensions['.ts'];
  extensions['.ts'] = (module, path) => {
    const source = require('node:fs').readFileSync(path, 'utf8') as string;
    (module as NodeModule & { _compile(code: string, path: string): void })._compile(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true } }).outputText, path);
  };
  try {
    const loaded = require(filename) as SsgConfig | { default: SsgConfig };
    return 'default' in loaded ? loaded.default : loaded;
  } finally {
    if (previous) extensions['.ts'] = previous;
    else delete extensions['.ts'];
  }
}

async function runHook(plugins: Plugin[], hook: keyof Plugin, context: BuildContext): Promise<void> {
  for (const plugin of plugins) await plugin[hook]?.(context);
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const context: BuildContext = { contentDir: resolve(options.contentDir ?? 'content'), outputDir: resolve(options.outputDir ?? 'dist'), templateDir: resolve(options.templateDir ?? 'templates'), pages: [] };
  const config = await loadConfig(resolve(options.configFile ?? 'ssg.config.ts'));
  const plugins = [MarkdownPlugin, ...(config.plugins ?? []), ...(options.plugins ?? []), new TemplatePlugin()];
  try {
    await runHook(plugins, 'onStart', context);
    await rm(context.outputDir, { recursive: true, force: true });
    await mkdir(context.outputDir, { recursive: true });
    await runHook(plugins, 'beforeBuild', context);
    for (const file of await markdownFiles(context.contentDir)) {
      context.source = await readFile(file, 'utf8');
      context.filename = relative(context.contentDir, file);
      context.page = undefined;
      await runHook(plugins, 'onFile', context);
      if (context.page) context.pages.push(context.page);
    }
    await runHook(plugins, 'afterBuild', context);
    return context.pages;
  } finally { await runHook(plugins, 'onEnd', context); }
}
